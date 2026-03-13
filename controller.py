import os
import select
import socket
import struct
import time
from typing import Optional, Tuple


# URFT: UDP-based Reliable File Transfer (assignment)
# - UDP only, single server socket
# - Reliable over loss/dup/reordering
# - Client sends filename first (META), then DATA, then END
# - Go-Back-N with cumulative ACKs


MAGIC = b"URFT"

TYPE_META = 1
TYPE_DATA = 2
TYPE_END = 3
TYPE_ACK = 4

# Packet header:
#   magic(4), type(1), seq(4), ack(4), payload_len(2)
_HDR = struct.Struct("!4sBIIH")
HDR_LEN = _HDR.size

# Keep UDP datagrams well under typical MTU (simple + safe).
MAX_PACKET = 1400
MAX_PAYLOAD = MAX_PACKET - HDR_LEN


def _pack(ptype: int, seq: int, ack: int, payload: bytes) -> bytes:
    if payload is None:
        payload = b""
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("payload too large")
    return _HDR.pack(MAGIC, int(ptype), int(seq), int(ack), len(payload)) + payload


def _unpack(data: bytes) -> Optional[Tuple[int, int, int, bytes]]:
    if len(data) < HDR_LEN:
        return None
    magic, ptype, seq, ack, plen = _HDR.unpack(data[:HDR_LEN])
    if magic != MAGIC:
        return None
    payload = data[HDR_LEN:]
    if plen != len(payload):
        return None
    return int(ptype), int(seq), int(ack), payload


class _UDPEndpoint:
    def __init__(self, sock: socket.socket):
        self._sock = sock

    def sendto(self, ptype: int, addr: Tuple[str, int], *, seq: int = 0, ack: int = 0, payload: bytes = b"") -> None:
        self._sock.sendto(_pack(ptype, seq, ack, payload), addr)

    def recvfrom(self, timeout_s: float) -> Tuple[Optional[Tuple[int, int, int, bytes]], Optional[Tuple[str, int]]]:
        r, _, _ = select.select([self._sock], [], [], max(0.0, timeout_s))
        if not r:
            return None, None
        data, addr = self._sock.recvfrom(MAX_PACKET)
        return _unpack(data), addr


class Server:
    """
    URFT server (UDP) that receives exactly one file then exits.
    Uses a single UDP socket as required.
    """

    def __init__(self, server_ip: str, server_port: int):
        self.__server_ip = server_ip
        self.__server_port = server_port
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__socket.bind((self.__server_ip, self.__server_port))
        self.__socket.setblocking(False)
        self.__ep = _UDPEndpoint(self.__socket)

    def receive(self) -> str:
        print(f"Server listening on {self.__server_ip}:{self.__server_port} (URFT/UDP)...")

        # Phase 1: receive META (seq=0) to learn filename and size.
        client_addr: Optional[Tuple[str, int]] = None
        expected_seq = 0
        file_name: Optional[str] = None
        expected_size: Optional[int] = None

        while True:
            msg, addr = self.__ep.recvfrom(timeout_s=1.0)
            if msg is None or addr is None:
                continue

            if client_addr is None:
                client_addr = addr
            if addr != client_addr:
                # Single-client requirement: ignore others.
                continue

            ptype, seq, _ack, payload = msg
            if ptype != TYPE_META or seq != 0:
                # Not ready yet: ACK current expectation.
                self.__ep.sendto(TYPE_ACK, client_addr, ack=expected_seq)
                continue

            try:
                meta = payload.decode("utf-8", errors="strict")
                # Format: "<filename>\n<filesize>\n"
                parts = meta.split("\n")
                raw_name = parts[0].strip()
                raw_size = parts[1].strip()
                if not raw_name:
                    raise ValueError("empty filename")
                expected_size = int(raw_size)
                if expected_size < 0:
                    raise ValueError("negative size")
                file_name = os.path.basename(raw_name)
                if not file_name:
                    raise ValueError("invalid filename")
            except Exception:
                # Bad metadata; keep waiting for a valid META.
                continue

            expected_seq = 1
            self.__ep.sendto(TYPE_ACK, client_addr, ack=expected_seq)
            break

        assert client_addr is not None and file_name is not None and expected_size is not None

        # Phase 2: receive DATA/END. Go-Back-N receiver: accept only in-order.
        received_bytes = 0
        out_path = file_name
        with open(out_path, "wb") as f:
            while True:
                msg, addr = self.__ep.recvfrom(timeout_s=1.0)
                if msg is None or addr is None:
                    # Re-ACK in case ACK was lost.
                    self.__ep.sendto(TYPE_ACK, client_addr, ack=expected_seq)
                    continue
                if addr != client_addr:
                    continue

                ptype, seq, _ack, payload = msg
                if ptype == TYPE_DATA:
                    if seq == expected_seq:
                        f.write(payload)
                        received_bytes += len(payload)
                        expected_seq += 1
                    # Cumulative ACK for next expected seq (handles dup/reorder).
                    self.__ep.sendto(TYPE_ACK, client_addr, ack=expected_seq)
                    continue

                if ptype == TYPE_END:
                    # Only finish if END is in-order.
                    if seq == expected_seq and received_bytes == expected_size:
                        expected_seq += 1
                        self.__ep.sendto(TYPE_ACK, client_addr, ack=expected_seq)
                        break
                    # Otherwise keep ACKing the expected sequence number.
                    self.__ep.sendto(TYPE_ACK, client_addr, ack=expected_seq)
                    continue

                # Unknown packet: just ACK.
                self.__ep.sendto(TYPE_ACK, client_addr, ack=expected_seq)

        print(f"Saved received file to {out_path} ({received_bytes} bytes)")
        return out_path


class Client:
    """
    URFT client (UDP) that sends one file then exits.
    """

    def __init__(self, server_ip: str, server_port: int):
        self.__server_ip = server_ip
        self.__server_port = server_port
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__socket.setblocking(False)
        self.__ep = _UDPEndpoint(self.__socket)
        self.__server_addr = (self.__server_ip, self.__server_port)

    def send_message(self, message: str) -> None:
        # Backwards-compatible entry point used by urft_client.py
        self.send_file(message)

    def send_file(
        self,
        file_path: str,
        *,
        window_size: int = 64,
        timeout_s: float = 0.25,
    ) -> None:
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        meta_payload = f"{file_name}\n{file_size}\n".encode("utf-8")

        # Stop-and-wait for META (seq=0)
        while True:
            t0 = time.monotonic()
            self.__ep.sendto(TYPE_META, self.__server_addr, seq=0, payload=meta_payload)
            msg, _ = self.__ep.recvfrom(timeout_s=timeout_s)
            if msg and msg[0] == TYPE_ACK and msg[2] == 1:
                # Calibrate timeout for high-RTT tests (e.g., 250ms).
                rtt = max(0.0, time.monotonic() - t0)
                # Conservative RTO: scales with RTT, bounded to avoid runaway.
                timeout_s = max(timeout_s, min(1.5, 2.5 * rtt + 0.05))
                break

        # Go-Back-N for DATA packets starting at seq=1.
        base = 1
        next_seq = 1
        def _send(seq: int, payload: bytes) -> None:
            self.__ep.sendto(TYPE_DATA, self.__server_addr, seq=seq, payload=payload)

        with open(file_path, "rb") as f:
            chunks = []
            while True:
                b = f.read(MAX_PAYLOAD)
                if not b:
                    break
                chunks.append(b)

        total_chunks = len(chunks)
        eof_seq = 1 + total_chunks

        while base < eof_seq:
            # Fill window
            while next_seq < eof_seq and next_seq < base + max(1, int(window_size)):
                _send(next_seq, chunks[next_seq - 1])
                next_seq += 1

            # Wait for ACK or timeout.
            msg, _ = self.__ep.recvfrom(timeout_s=timeout_s)
            if msg and msg[0] == TYPE_ACK:
                # Cumulative ACK: next expected data seq.
                ack = msg[2]
                if ack > base:
                    base = ack
                continue

            # Timeout: retransmit from base (GBN).
            for s in range(base, next_seq):
                _send(s, chunks[s - 1])

        # END handshake (seq=eof_seq)
        while True:
            self.__ep.sendto(TYPE_END, self.__server_addr, seq=eof_seq)
            msg, _ = self.__ep.recvfrom(timeout_s=timeout_s)
            if msg and msg[0] == TYPE_ACK and msg[2] == eof_seq + 1:
                break

        print(f"Sent file: {file_path} ({file_size} bytes)")
