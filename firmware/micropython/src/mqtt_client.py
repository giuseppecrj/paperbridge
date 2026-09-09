# Derived from micropython-lib umqtt.simple 1.8.0, commit
# 5e49b1bd41d312d9d2a8e4f19d7bd6a918896abc. Originally by Paul Sokolovsky.
# Paperbridge changes: bounded PUBLISH decoding, retain flag in callbacks,
# malformed-packet rejection and deterministic close on receive failure.
# Source and deployment details: docs/mqtt-client.md.
#
# The MIT License (MIT)
# Copyright (c) 2013, 2014 micropython-lib contributors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import socket
import struct


class MQTTException(Exception):
    pass


def _encode_len(pkt, sz):
    i = 1
    while sz > 0x7F:
        pkt[i] = (sz & 0x7F) | 0x80
        sz >>= 7
        i += 1
    pkt[i] = sz
    return i


class MQTTClient:
    def __init__(
        self,
        client_id,
        server,
        port=0,
        user=None,
        password=None,
        keepalive=0,
        ssl=None,
        ssl_params=None,
        max_message_bytes=65_536,
        max_topic_bytes=256,
    ):
        if port == 0:
            port = 8883 if ssl else 1883
        self.client_id = client_id
        self.sock = None
        self.server = server
        self.port = port
        self.ssl = ssl
        self.ssl_params = ssl_params or {}
        self.max_message_bytes = max_message_bytes
        self.max_topic_bytes = max_topic_bytes
        self.pid = 0
        self.cb = None
        self.user = user
        self.pswd = password
        self.keepalive = keepalive
        self.lw_topic = None
        self.lw_msg = None
        self.lw_qos = 0
        self.lw_retain = False

    def _send_str(self, s):
        self.sock.write(struct.pack("!H", len(s)))
        self.sock.write(s)

    def _recv_len(self):
        n = 0
        for sh in (0, 7, 14, 21):
            b = self._read_exact(1)[0]
            n |= (b & 0x7F) << sh
            if not b & 0x80:
                if sh and b == 0:
                    raise MQTTException("INVALID_MQTT_PACKET")
                return n
        raise MQTTException("INVALID_MQTT_PACKET")

    def _read_exact(self, size):
        if size == 0:
            return b""
        value = self.sock.read(size)
        if value is None or len(value) != size:
            raise MQTTException("INVALID_MQTT_PACKET")
        return value

    def set_callback(self, f):
        self.cb = f

    def set_last_will(self, topic, msg, retain=False, qos=0):
        assert 0 <= qos <= 2
        assert topic
        self.lw_topic = topic
        self.lw_msg = msg
        self.lw_qos = qos
        self.lw_retain = retain

    def connect(self, clean_session=True, timeout=None):
        if self.sock:
            self.sock.close()
        self.sock = socket.socket()
        self.sock.settimeout(timeout)
        addr = socket.getaddrinfo(self.server, self.port)[0][-1]
        self.sock.connect(addr)
        if self.ssl is True:
            # Legacy support for ssl=True and ssl_params arguments.
            import ssl

            self.sock = ssl.wrap_socket(self.sock, **self.ssl_params)
        elif self.ssl:
            self.sock = self.ssl.wrap_socket(self.sock, server_hostname=self.server)
        premsg = bytearray(b"\x10\0\0\0\0\0")
        msg = bytearray(b"\x04MQTT\x04\x02\0\0")

        sz = 10 + 2 + len(self.client_id)
        msg[6] = clean_session << 1
        if self.user:
            sz += 2 + len(self.user) + 2 + len(self.pswd)
            msg[6] |= 0xC0
        if self.keepalive:
            assert self.keepalive < 65536
            msg[7] |= self.keepalive >> 8
            msg[8] |= self.keepalive & 0x00FF
        if self.lw_topic:
            sz += 2 + len(self.lw_topic) + 2 + len(self.lw_msg)
            msg[6] |= 0x4 | (self.lw_qos & 0x1) << 3 | (self.lw_qos & 0x2) << 3
            msg[6] |= self.lw_retain << 5

        i = _encode_len(premsg, sz)

        self.sock.write(premsg, i + 2)
        self.sock.write(msg)
        self._send_str(self.client_id)
        if self.lw_topic:
            self._send_str(self.lw_topic)
            self._send_str(self.lw_msg)
        if self.user:
            self._send_str(self.user)
            self._send_str(self.pswd)
        resp = self.sock.read(4)
        assert resp[0] == 0x20 and resp[1] == 0x02
        if resp[3] != 0:
            raise MQTTException(resp[3])
        return resp[2] & 1

    def disconnect(self):
        self.sock.write(b"\xe0\0")
        self.sock.close()

    def ping(self):
        self.sock.write(b"\xc0\0")

    def publish(self, topic, msg, retain=False, qos=0):
        pkt = bytearray(b"\x30\0\0\0")
        pkt[0] |= qos << 1 | retain
        sz = 2 + len(topic) + len(msg)
        if qos > 0:
            sz += 2
        assert sz < 2097152
        i = _encode_len(pkt, sz)
        self.sock.write(pkt, i + 1)
        self._send_str(topic)
        if qos > 0:
            self.pid += 1
            pid = self.pid
            struct.pack_into("!H", pkt, 0, pid)
            self.sock.write(pkt, 2)
        self.sock.write(msg)
        if qos == 1:
            while 1:
                op = self.wait_msg()
                if op == 0x40:
                    sz = self.sock.read(1)
                    assert sz == b"\x02"
                    rcv_pid = self.sock.read(2)
                    rcv_pid = rcv_pid[0] << 8 | rcv_pid[1]
                    if pid == rcv_pid:
                        return
        elif qos == 2:
            assert 0

    def _send_subunsub(self, topic, typ, ack_op, ack_n, qos=0):
        pkt = bytearray(4)
        pkt[0] = typ
        self.pid += 1
        pid = self.pid
        i = _encode_len(pkt, 4 + len(topic) + (ack_n > 3))
        self.sock.write(pkt, i + 1)
        struct.pack_into("!H", pkt, 0, pid)
        self.sock.write(pkt, 2)
        self._send_str(topic)
        if ack_n > 3:
            self.sock.write(bytes((qos,)))
        while 1:
            op = self.wait_msg()
            if op == ack_op:
                resp = self.sock.read(ack_n)
                assert (resp[1] << 8 | resp[2]) == pid
                if ack_n > 3 and resp[3] == 0x80:
                    raise MQTTException(resp[3])
                return

    def subscribe(self, topic, qos=0):
        assert self.cb is not None, "Subscribe callback is not set"
        self._send_subunsub(topic, 0x82, 0x90, 4, qos)

    def unsubscribe(self, topic):
        self._send_subunsub(topic, 0xA2, 0xB0, 3)

    # Wait for a single incoming MQTT message and process it.
    # Subscribed messages are delivered to a callback previously
    # set by .set_callback() method. Other (internal) MQTT
    # messages processed internally.
    def wait_msg(self):
        try:
            return self._wait_msg()
        except Exception:
            # The stream cannot be resynchronized after a rejected length.
            self.sock.close()
            raise

    def _wait_msg(self):
        res = self.sock.read(1)
        self.sock.setblocking(True)
        if res is None:
            return None
        if res == b"":
            raise OSError(-1)
        if res == b"\xd0":  # PINGRESP
            sz = self.sock.read(1)[0]
            assert sz == 0
            return None
        op = res[0]
        if op & 0xF0 != 0x30:
            return op
        sz = self._recv_len()
        # Remaining Length includes the topic length, topic, and QoS packet ID.
        # Reject it before reading any attacker-sized topic or payload.
        if sz > self.max_message_bytes + self.max_topic_bytes + 4:
            raise MQTTException("MQTT_PACKET_TOO_LARGE")
        qos = (op >> 1) & 3
        if qos > 1 or sz < 2:
            raise MQTTException("INVALID_MQTT_PACKET")
        topic_len = self._read_exact(2)
        topic_len = (topic_len[0] << 8) | topic_len[1]
        payload_size = sz - topic_len - 2 - (2 if qos else 0)
        if not 0 < topic_len <= self.max_topic_bytes or payload_size < 0:
            raise MQTTException("INVALID_MQTT_PACKET")
        if payload_size > self.max_message_bytes:
            raise MQTTException("MQTT_PAYLOAD_TOO_LARGE")
        topic = self._read_exact(topic_len)
        if qos:
            pid = self._read_exact(2)
            pid = pid[0] << 8 | pid[1]
            if pid == 0:
                raise MQTTException("INVALID_MQTT_PACKET")
        msg = self._read_exact(payload_size)
        self.cb(topic, msg, bool(op & 1))
        if qos == 1:
            pkt = bytearray(b"\x40\x02\0\0")
            struct.pack_into("!H", pkt, 2, pid)
            self.sock.write(pkt)
        return op

    # Checks whether a pending message from server is available.
    # If not, returns immediately with None. Otherwise, does
    # the same processing as wait_msg.
    def check_msg(self):
        self.sock.setblocking(False)
        return self.wait_msg()
