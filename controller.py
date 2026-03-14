import os
import select
import socket
import struct
import time
from typing import Optional, Tuple


MAGIC = b"URFT"

TYPE_META = 1
TYPE_DATA = 2
TYPE_END = 3
TYPE_ACK = 4

_HDR = struct.Struct("!4sBIIH")
HDR_LEN = _HDR.size

# Keep payloads under typical MTU to avoid fragmentation.
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
    """URFT UDP server for one file."""

    def __init__(self, server_ip: str, server_port: int):
        self.__server_ip = server_ip
        self.__server_port = server_port
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__socket.bind((self.__server_ip, self.__server_port))
        self.__socket.setblocking(False)
        self.__ep = _UDPEndpoint(self.__socket)

    def receive(self) -> str:
        print(f"Server listening on {self.__server_ip}:{self.__server_port} (URFT/UDP)...")

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
                continue

            ptype, seq, _ack, payload = msg
            if ptype != TYPE_META or seq != 0:
                self.__ep.sendto(TYPE_ACK, client_addr, ack=expected_seq)
                continue

            try:
                meta = payload.decode("utf-8", errors="strict")
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
                continue

            expected_seq = 1
            self.__ep.sendto(TYPE_ACK, client_addr, ack=expected_seq)
            break

        assert client_addr is not None and file_name is not None and expected_size is not None

        # Selective repeat: ACK each DATA seq and buffer out-of-order chunks.
        received_bytes = 0
        total_chunks = (expected_size + MAX_PAYLOAD - 1) // MAX_PAYLOAD
        end_seq = total_chunks + 1
        next_write_seq = 1
        out_of_order = {}
        out_path = file_name
        with open(out_path, "wb") as f:
            while True:
                msg, addr = self.__ep.recvfrom(timeout_s=0.2)
                if msg is None or addr is None:
                    continue
                if addr != client_addr:
                    continue

                ptype, seq, _ack, payload = msg
                if ptype == TYPE_META and seq == 0:
                    # Re-ACK duplicate META if initial ACK was lost.
                    self.__ep.sendto(TYPE_ACK, client_addr, ack=1)
                    continue

                if ptype == TYPE_DATA:
                    if seq < 1 or seq > total_chunks:
                        continue

                    self.__ep.sendto(TYPE_ACK, client_addr, ack=seq)

                    if seq == next_write_seq:
                        f.write(payload)
                        received_bytes += len(payload)
                        next_write_seq += 1
                        while next_write_seq in out_of_order:
                            cached = out_of_order.pop(next_write_seq)
                            f.write(cached)
                            received_bytes += len(cached)
                            next_write_seq += 1
                    elif seq > next_write_seq:
                        if seq not in out_of_order:
                            out_of_order[seq] = payload
                    continue

                if ptype == TYPE_END:
                    if seq == end_seq and next_write_seq == end_seq and received_bytes == expected_size:
                        # Repeat final ACK to reduce tail-loss risk.
                        for _ in range(4):
                            self.__ep.sendto(TYPE_ACK, client_addr, ack=end_seq)
                        break
                    continue

                continue

        print(f"Saved received file to {out_path} ({received_bytes} bytes)")
        print("File transfer completed.")
        return out_path


class Client:
    """URFT UDP client for one file."""

    def __init__(self, server_ip: str, server_port: int):
        self.__server_ip = server_ip
        self.__server_port = server_port
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__socket.setblocking(False)
        self.__ep = _UDPEndpoint(self.__socket)
        self.__server_addr = (self.__server_ip, self.__server_port)

    def send_message(self, message: str) -> None:
        self.send_file(message)

    def send_file(
        self,
        file_path: str,
        *,
        window_size: int = 512,
        timeout_s: float = 0.15,
    ) -> None:
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        meta_payload = f"{file_name}\n{file_size}\n".encode("utf-8")

        while True:
            t0 = time.monotonic()
            self.__ep.sendto(TYPE_META, self.__server_addr, seq=0, payload=meta_payload)
            msg, _ = self.__ep.recvfrom(timeout_s=timeout_s)
            if msg and msg[0] == TYPE_ACK and msg[2] == 1:
                rtt = max(0.0, time.monotonic() - t0)
                timeout_s = max(0.08, min(0.6, 1.8 * rtt + 0.02))
                break

        # Read file into fixed-size chunks.
        with open(file_path, "rb") as f:
            chunks = []
            while True:
                b = f.read(MAX_PAYLOAD)
                if not b:
                    break
                chunks.append(b)

        total_chunks = len(chunks)
        eof_seq = 1 + total_chunks

        base = 1
        next_seq = 1
        acked = set()
        sent_at = {}

        def _send(seq: int) -> None:
            self.__ep.sendto(TYPE_DATA, self.__server_addr, seq=seq, payload=chunks[seq - 1])
            sent_at[seq] = time.monotonic()

        while base <= total_chunks:
            while next_seq <= total_chunks and next_seq < base + max(1, int(window_size)):
                _send(next_seq)
                next_seq += 1

            # Read ACKs; ack field is the DATA sequence number.
            msg, _ = self.__ep.recvfrom(timeout_s=0.01)
            while msg is not None:
                if msg[0] == TYPE_ACK:
                    ack_seq = msg[2]
                    if 1 <= ack_seq <= total_chunks:
                        if ack_seq not in acked:
                            acked.add(ack_seq)
                        while base in acked:
                            base += 1
                msg, _ = self.__ep.recvfrom(timeout_s=0.0)

            now = time.monotonic()
            for s in range(base, next_seq):
                if s in acked:
                    continue
                last = sent_at.get(s, 0.0)
                if now - last >= timeout_s:
                    _send(s)

        while True:
            self.__ep.sendto(TYPE_END, self.__server_addr, seq=eof_seq)
            msg, _ = self.__ep.recvfrom(timeout_s=timeout_s)
            if msg and msg[0] == TYPE_ACK and msg[2] == eof_seq:
                break

        print(f"Sent file: {file_path} ({file_size} bytes)")
