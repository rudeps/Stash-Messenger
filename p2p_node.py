import os
import sys
import json
import socket
import threading
import time
import queue
import random
import math
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
from crypto_utils import sha256, verify_signature, sign_data
from database import Database, Contact, Message

K = 20
ALPHA = 3
REPLICATION = 3

def distance(a: bytes, b: bytes) -> int:
    return int.from_bytes(a, 'big') ^ int.from_bytes(b, 'big')

class P2PNode:
    def __init__(self, port: int, node_id: bytes, username: str,
                 public_key: bytes, private_key, db: Database):
        self.port = port
        self.node_id = node_id
        self.username = username
        self.public_key = public_key
        self.private_key = private_key
        self.db = db
        self.username_hash = sha256(username.encode())
        self.running = False
        self.socket = None
        self.peers: Dict[str, Tuple[str, int, float]] = {}
        self.buckets = [ [] for _ in range(256) ]
        self.message_queue = queue.Queue()
        self.callbacks = []
        self.listener_thread = None
        self.processor_thread = None
        self.stabilize_thread = None

    def start(self):
        self.running = True
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.socket.bind(('0.0.0.0', self.port))
        except OSError as e:
            print(f"[ERROR] Cannot bind port {self.port}: {e}")
            sys.exit(1)
        self.listener_thread = threading.Thread(target=self._listen, daemon=True)
        self.processor_thread = threading.Thread(target=self._process, daemon=True)
        self.stabilize_thread = threading.Thread(target=self._stabilize_loop, daemon=True)
        self.listener_thread.start()
        self.processor_thread.start()
        self.stabilize_thread.start()
        print(f"[P2P] Node {self.node_id.hex()[:8]} started on port {self.port}")

    def stop(self):
        self.running = False
        if self.socket:
            self.socket.close()

    def _listen(self):
        while self.running:
            try:
                data, addr = self.socket.recvfrom(65535)
                self.message_queue.put((data, addr))
            except:
                pass

    def _process(self):
        while self.running:
            try:
                data, addr = self.message_queue.get(timeout=0.1)
                self._handle_message(data, addr)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[ERROR] Process: {e}")

    def _send_to(self, ip: str, port: int, data: bytes):
        try:
            self.socket.sendto(data, (ip, port))
        except:
            pass

    def _sign_contact_info(self) -> bytes:
        data = self.username_hash + self.public_key + self.node_id
        return sign_data(self.private_key, data)

    def _handle_message(self, data: bytes, addr: Tuple[str, int]):
        try:
            msg = json.loads(data.decode())
        except:
            return
        mtype = msg.get('type')
        if mtype == 'HELLO':
            self._handle_hello(msg, addr)
        elif mtype == 'PING':
            self._handle_ping(msg, addr)
        elif mtype == 'PONG':
            self._handle_pong(msg, addr)
        elif mtype == 'FIND_NODE':
            self._handle_find_node(msg, addr)
        elif mtype == 'NODES':
            self._handle_nodes(msg, addr)
        elif mtype == 'FIND_VALUE':
            self._handle_find_value(msg, addr)
        elif mtype == 'VALUE':
            self._handle_value(msg, addr)
        elif mtype == 'STORE':
            self._handle_store(msg, addr)
        elif mtype == 'RETRIEVE_MESSAGES':
            self._handle_retrieve_messages(msg, addr)
        elif mtype == 'MESSAGE':
            self._handle_message_receive(msg, addr)
        elif mtype == 'SYNC_CONTACTS_REQUEST':
            self._handle_sync_contacts_request(msg, addr)
        elif mtype == 'SYNC_CONTACTS_RESPONSE':
            self._handle_sync_contacts_response(msg, addr)

    def _handle_hello(self, msg, addr):
        node_id = bytes.fromhex(msg['node_id'])
        username = msg['username']
        peer_port = msg['port']
        pubkey = bytes.fromhex(msg.get('public_key', ''))
        signature = bytes.fromhex(msg.get('signature', ''))

        if pubkey:
            username_hash = sha256(username.encode())
            data_to_verify = username_hash + pubkey + node_id
            if verify_signature(pubkey, signature, data_to_verify):
                contact = Contact(
                    username=username,
                    username_hash=username_hash,
                    public_key=pubkey,
                    node_id=node_id,
                    last_seen=time.time(),
                    last_ip=addr[0],
                    last_port=peer_port,
                    signature=signature
                )
                self.db.save_contact(contact)
                self.db.ensure_chat(username)
                self._trigger_callbacks('contact_found', username)
            else:
                print(f"[WARN] Invalid signature in HELLO from {username}")
        self._add_peer(node_id, addr[0], peer_port)

        sig = self._sign_contact_info().hex()
        resp = {
            'type': 'HELLO',
            'node_id': self.node_id.hex(),
            'username': self.username,
            'port': self.port,
            'public_key': self.public_key.hex(),
            'signature': sig
        }
        self._send_to(addr[0], peer_port, json.dumps(resp).encode())

    def _handle_ping(self, msg, addr):
        resp = {'type': 'PONG', 'node_id': self.node_id.hex()}
        self._send_to(addr[0], addr[1], json.dumps(resp).encode())

    def _handle_pong(self, msg, addr):
        pass

    def _handle_find_node(self, msg, addr):
        target = bytes.fromhex(msg['target'])
        closest = self._get_closest_nodes(target, K)
        resp = {'type': 'NODES', 'nodes': [(ip, port) for _, (ip, port, _) in closest]}
        self._send_to(addr[0], addr[1], json.dumps(resp).encode())

    def _handle_nodes(self, msg, addr):
        pass

    def _handle_find_value(self, msg, addr):
        key = msg['key']
        contact = None
        for c in self.db.get_all_contacts():
            if c.username_hash.hex() == key:
                contact = c
                break
        if contact:
            value = {
                'username': contact.username,
                'public_key': contact.public_key.hex(),
                'node_id': contact.node_id.hex(),
                'last_seen': contact.last_seen,
                'signature': contact.signature.hex()
            }
            resp = {'type': 'VALUE', 'key': key, 'value': value}
            self._send_to(addr[0], addr[1], json.dumps(resp).encode())
        else:
            closest = self._get_closest_nodes(bytes.fromhex(key), K)
            resp = {'type': 'NODES', 'nodes': [(ip, port) for _, (ip, port, _) in closest]}
            self._send_to(addr[0], addr[1], json.dumps(resp).encode())

    def _handle_value(self, msg, addr):
        key = msg['key']
        value = msg['value']
        pubkey = bytes.fromhex(value['public_key'])
        node_id = bytes.fromhex(value['node_id'])
        username_hash = bytes.fromhex(key)
        sig = bytes.fromhex(value['signature'])
        data_to_verify = username_hash + pubkey + node_id
        if verify_signature(pubkey, sig, data_to_verify):
            contact = Contact(
                username=value['username'],
                username_hash=username_hash,
                public_key=pubkey,
                node_id=node_id,
                last_seen=value['last_seen'],
                last_ip='',
                last_port=0,
                signature=sig
            )
            self.db.save_contact(contact)
            self.db.ensure_chat(contact.username)
            self._trigger_callbacks('contact_found', contact.username)
        else:
            print("[WARN] Invalid signature in VALUE")

    def _handle_store(self, msg, addr):
        recipient_node_id = bytes.fromhex(msg['recipient_node_id'])
        if self._am_i_responsible(recipient_node_id):
            self.db.store_offline_message(
                msg['msg_id'],
                recipient_node_id,
                bytes.fromhex(msg['encrypted_blob']),
                msg['timestamp']
            )
            self._replicate_message(msg)

    def _handle_retrieve_messages(self, msg, addr):
        requester_node_id = bytes.fromhex(msg['node_id'])
        msgs = self.db.get_offline_messages(requester_node_id)
        for msg_id, blob in msgs:
            resp = {
                'type': 'MESSAGE',
                'msg_id': msg_id,
                'encrypted_blob': blob.hex()
            }
            self._send_to(addr[0], addr[1], json.dumps(resp).encode())

    def _handle_message_receive(self, msg, addr):
        if 'content' in msg:
            message = Message(
                msg_id=msg['msg_id'],
                sender_username=msg['sender'],
                recipient_username=msg['recipient'],
                content=msg['content'],
                timestamp=msg['timestamp'],
                signature=bytes.fromhex(msg['signature'])
            )
            self.db.save_message(message)
            self._trigger_callbacks('message', message)
        elif 'encrypted_blob' in msg:
            pass

    def _handle_sync_contacts_request(self, msg, addr):
        contacts = self.db.get_all_contacts()
        data = b''.join(c.username_hash + c.public_key + c.node_id for c in contacts)
        hash_sum = sha256(data).hex()
        resp = {'type': 'SYNC_CONTACTS_RESPONSE', 'hash': hash_sum, 'count': len(contacts)}
        self._send_to(addr[0], addr[1], json.dumps(resp).encode())

    def _handle_sync_contacts_response(self, msg, addr):
        pass

    def _get_bucket_index(self, node_id: bytes) -> int:
        dist = distance(self.node_id, node_id)
        if dist == 0:
            return 0
        return int(math.log2(dist))

    def _add_peer(self, node_id: bytes, ip: str, port: int):
        idx = self._get_bucket_index(node_id)
        bucket = self.buckets[idx]
        for nid, (_, _, _) in bucket:
            if nid == node_id:
                return
        if len(bucket) < K:
            bucket.append((node_id, (ip, port, time.time())))
        else:
            pass
        self.peers[node_id.hex()] = (ip, port, time.time())

    def _get_closest_nodes(self, target: bytes, count: int) -> List[Tuple[bytes, Tuple[str, int, float]]]:
        all_nodes = []
        for bucket in self.buckets:
            all_nodes.extend(bucket)
        all_nodes.sort(key=lambda x: distance(x[0], target))
        return all_nodes[:count]

    def _am_i_responsible(self, key: bytes) -> bool:
        closest = self._get_closest_nodes(key, REPLICATION)
        my_dist = distance(self.node_id, key)
        for nid, _ in closest:
            if distance(nid, key) < my_dist:
                return False
        return True

    def _replicate_message(self, store_msg: dict):
        recipient_id = bytes.fromhex(store_msg['recipient_node_id'])
        closest = self._get_closest_nodes(recipient_id, REPLICATION + 1)
        for nid, (ip, port, _) in closest:
            if nid == self.node_id:
                continue
            self._send_to(ip, port, json.dumps(store_msg).encode())

    def _stabilize_loop(self):
        while self.running:
            time.sleep(30)
            self._retrieve_offline_messages()

    def _retrieve_offline_messages(self):
        closest = self._get_closest_nodes(self.node_id, REPLICATION)
        req = {'type': 'RETRIEVE_MESSAGES', 'node_id': self.node_id.hex()}
        for nid, (ip, port, _) in closest:
            if nid == self.node_id:
                continue
            self._send_to(ip, port, json.dumps(req).encode())

    def connect_to_peer(self, ip: str, port: int):
        sig = self._sign_contact_info().hex()
        hello = {
            'type': 'HELLO',
            'node_id': self.node_id.hex(),
            'username': self.username,
            'port': self.port,
            'public_key': self.public_key.hex(),
            'signature': sig
        }
        self._send_to(ip, port, json.dumps(hello).encode())

    def find_user(self, username: str):
        target = sha256(username.encode()).hex()
        req = {'type': 'FIND_VALUE', 'key': target}
        for ip, port, _ in self.peers.values():
            self._send_to(ip, port, json.dumps(req).encode())

    def send_message(self, recipient: str, content: str) -> bool:
        contact = self.db.get_contact(recipient)
        if not contact:
            return False
        msg_id = sha256(f"{self.username}{recipient}{content}{time.time()}".encode()).hex()[:16]
        msg = {
            'type': 'MESSAGE',
            'msg_id': msg_id,
            'sender': self.username,
            'recipient': recipient,
            'content': content,
            'timestamp': time.time(),
            'signature': b''.hex()
        }
        if contact.last_ip and (time.time() - contact.last_seen) < 300:
            self._send_to(contact.last_ip, contact.last_port, json.dumps(msg).encode())
        else:
            self._store_offline_message(contact.node_id, msg)
        message = Message(
            msg_id=msg_id,
            sender_username=self.username,
            recipient_username=recipient,
            content=content,
            timestamp=msg['timestamp'],
            signature=b''
        )
        self.db.save_message(message)
        self._trigger_callbacks('message_sent', message)
        return True

    def _store_offline_message(self, recipient_node_id: bytes, msg: dict):
        encrypted_blob = json.dumps(msg).encode()
        store_msg = {
            'type': 'STORE',
            'msg_id': msg['msg_id'],
            'recipient_node_id': recipient_node_id.hex(),
            'encrypted_blob': encrypted_blob.hex(),
            'timestamp': msg['timestamp']
        }
        closest = self._get_closest_nodes(recipient_node_id, REPLICATION)
        for nid, (ip, port, _) in closest:
            self._send_to(ip, port, json.dumps(store_msg).encode())

    def add_callback(self, cb):
        self.callbacks.append(cb)

    def _trigger_callbacks(self, event_type, data):
        for cb in self.callbacks:
            try:
                cb(event_type, data)
            except:
                pass
