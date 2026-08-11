#!/usr/bin/env python3
"""Build a SIPp-playable Ethernet/IPv4/UDP/RTP PCAP from 8 kHz PCMU audio."""

import argparse
import struct
import time


def checksum(data):
    if len(data) % 2:
        data += b'\0'
    value = sum(struct.unpack('!{}H'.format(len(data) // 2), data))
    value = (value >> 16) + (value & 0xffff)
    value += value >> 16
    return (~value) & 0xffff


def packet(sequence, timestamp, payload):
    rtp = struct.pack('!BBHII', 0x80, 0, sequence, timestamp, 0x13572468)
    udp_length = 8 + len(rtp) + len(payload)
    udp = struct.pack('!HHHH', 6000, 6002, udp_length, 0)
    total_length = 20 + udp_length
    ip = struct.pack(
        '!BBHHHBBH4s4s', 0x45, 0, total_length, sequence, 0, 64, 17, 0,
        b'\xc0\x00\x02\x0a', b'\xc0\x00\x02\x14',
    )
    ip = ip[:10] + struct.pack('!H', checksum(ip)) + ip[12:]
    ethernet = b'\x02\x00\x00\x00\x00\x02\x02\x00\x00\x00\x00\x01\x08\x00'
    return ethernet + ip + udp + rtp + payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input')
    parser.add_argument('output')
    args = parser.parse_args()
    audio = open(args.input, 'rb').read()
    if not audio:
        raise SystemExit('input audio is empty')
    audio += b'\xff' * ((-len(audio)) % 160)
    start = int(time.time())
    with open(args.output, 'wb') as output:
        output.write(struct.pack('<IHHIIII', 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
        for index in range(0, len(audio), 160):
            payload = audio[index:index + 160]
            frame = packet(index // 160, index, payload)
            seconds = start + index // 8000
            microseconds = (index % 8000) * 125
            output.write(struct.pack('<IIII', seconds, microseconds, len(frame), len(frame)))
            output.write(frame)


if __name__ == '__main__':
    main()
