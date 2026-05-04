"""
Модуль работы с базой данных SQLite.
"""
import os
import sqlite3
import json
import time
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from crypto_utils import sha256

@dataclass
class Message:
    msg_id: str
    sender_username: str
    recipient_username: str
    content: str
    timestamp: float
    signature: bytes

    def to_dict(self):
        d = asdict(self)
        d['signature'] = d['signature'].hex()
        return d

    @classmethod
    def from_dict(cls, data):
        data['signature'] = bytes.fromhex(data['signature'])
        return cls(**data)

@dataclass
class Contact:
    username: str
    username_hash: bytes
    public_key: bytes
    node_id: bytes
    last_seen: float
    last_ip: str
    last_port: int
    signature: bytes = b''

    def to_dict(self):
        d = asdict(self)
        for field in ['username_hash', 'public_key', 'node_id', 'signature']:
            d[field] = d[field].hex()
        return d

    @classmethod
    def from_dict(cls, data):
        for field in ['username_hash', 'public_key', 'node_id', 'signature']:
            data[field] = bytes.fromhex(data[field])
        return cls(**data)

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        cur = self.conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS user (
                username TEXT PRIMARY KEY,
                password_hash TEXT,
                mnemonic_encrypted TEXT,
                private_key BLOB,
                public_key BLOB
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS contacts (
                username TEXT PRIMARY KEY,
                username_hash TEXT,
                public_key TEXT,
                node_id TEXT,
                last_seen REAL,
                last_ip TEXT,
                last_port INTEGER,
                signature TEXT
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                msg_id TEXT PRIMARY KEY,
                sender_username TEXT,
                recipient_username TEXT,
                content TEXT,
                timestamp REAL,
                signature TEXT,
                is_read INTEGER DEFAULT 0
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS chats (
                contact_username TEXT PRIMARY KEY,
                last_message_time REAL,
                unread_count INTEGER DEFAULT 0
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS stored_messages (
                msg_id TEXT PRIMARY KEY,
                recipient_node_id TEXT,
                encrypted_blob BLOB,
                timestamp REAL,
                ttl REAL DEFAULT 172800
            )
        ''')
        self.conn.commit()

    def save_user(self, username, pwd_hash, mnem_enc, priv, pub):
        cur = self.conn.cursor()
        cur.execute('INSERT OR REPLACE INTO user VALUES (?,?,?,?,?)',
                    (username, pwd_hash, mnem_enc, priv, pub))
        self.conn.commit()

    def get_user(self, username: str) -> Optional[Dict]:
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM user WHERE username = ?', (username,))
        row = cur.fetchone()
        return dict(row) if row else None

    def save_contact(self, contact: Contact):
        cur = self.conn.cursor()
        cur.execute('''
            INSERT OR REPLACE INTO contacts
            VALUES (?,?,?,?,?,?,?,?)
        ''', (contact.username, contact.username_hash.hex(),
              contact.public_key.hex(), contact.node_id.hex(),
              contact.last_seen, contact.last_ip, contact.last_port,
              contact.signature.hex()))
        self.conn.commit()

    def get_contact(self, username: str) -> Optional[Contact]:
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM contacts WHERE username = ?', (username,))
        row = cur.fetchone()
        if row:
            return Contact(
                username=row['username'],
                username_hash=bytes.fromhex(row['username_hash']),
                public_key=bytes.fromhex(row['public_key']),
                node_id=bytes.fromhex(row['node_id']),
                last_seen=row['last_seen'],
                last_ip=row['last_ip'],
                last_port=row['last_port'],
                signature=bytes.fromhex(row['signature'])
            )
        return None

    def get_all_contacts(self) -> List[Contact]:
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM contacts')
        contacts = []
        for row in cur.fetchall():
            contacts.append(Contact(
                username=row['username'],
                username_hash=bytes.fromhex(row['username_hash']),
                public_key=bytes.fromhex(row['public_key']),
                node_id=bytes.fromhex(row['node_id']),
                last_seen=row['last_seen'],
                last_ip=row['last_ip'],
                last_port=row['last_port'],
                signature=bytes.fromhex(row['signature'])
            ))
        return contacts

    def save_message(self, msg: Message):
        cur = self.conn.cursor()
        cur.execute('''
            INSERT OR REPLACE INTO messages
            (msg_id, sender_username, recipient_username, content, timestamp, signature)
            VALUES (?,?,?,?,?,?)
        ''', (msg.msg_id, msg.sender_username, msg.recipient_username,
              msg.content, msg.timestamp, msg.signature.hex()))
        contact = msg.sender_username if msg.sender_username != self.get_my_username() else msg.recipient_username
        cur.execute('''
            INSERT INTO chats (contact_username, last_message_time, unread_count)
            VALUES (?,?,1)
            ON CONFLICT(contact_username) DO UPDATE SET
                last_message_time = excluded.last_message_time,
                unread_count = unread_count + 1
        ''', (contact, msg.timestamp))
        self.conn.commit()

    def get_chat_history(self, contact: str, limit=50) -> List[Message]:
        cur = self.conn.cursor()
        cur.execute('''
            SELECT * FROM messages
            WHERE sender_username = ? OR recipient_username = ?
            ORDER BY timestamp ASC LIMIT ?
        ''', (contact, contact, limit))
        msgs = []
        for row in cur.fetchall():
            msgs.append(Message(
                msg_id=row['msg_id'],
                sender_username=row['sender_username'],
                recipient_username=row['recipient_username'],
                content=row['content'],
                timestamp=row['timestamp'],
                signature=bytes.fromhex(row['signature'])
            ))
        cur.execute('UPDATE messages SET is_read=1 WHERE sender_username=? AND is_read=0', (contact,))
        cur.execute('UPDATE chats SET unread_count=0 WHERE contact_username=?', (contact,))
        self.conn.commit()
        return msgs

    def get_chats(self) -> List[Tuple[str, float, int]]:
        cur = self.conn.cursor()
        cur.execute('SELECT contact_username, last_message_time, unread_count FROM chats ORDER BY last_message_time DESC')
        return [(r[0], r[1], r[2]) for r in cur.fetchall()]

    def get_my_username(self) -> Optional[str]:
        cur = self.conn.cursor()
        cur.execute('SELECT username FROM user LIMIT 1')
        row = cur.fetchone()
        return row[0] if row else None

    def store_offline_message(self, msg_id: str, recipient_node_id: bytes, encrypted_blob: bytes, timestamp: float):
        cur = self.conn.cursor()
        cur.execute('''
            INSERT OR REPLACE INTO stored_messages (msg_id, recipient_node_id, encrypted_blob, timestamp)
            VALUES (?,?,?,?)
        ''', (msg_id, recipient_node_id.hex(), encrypted_blob, timestamp))
        self.conn.commit()

    def get_offline_messages(self, recipient_node_id: bytes) -> List[Tuple[str, bytes]]:
        cur = self.conn.cursor()
        cur.execute('''
            SELECT msg_id, encrypted_blob FROM stored_messages
            WHERE recipient_node_id = ? AND timestamp + ttl > ?
        ''', (recipient_node_id.hex(), time.time()))
        rows = cur.fetchall()
        return [(row[0], row[1]) for row in rows]

    def delete_offline_message(self, msg_id: str):
        cur = self.conn.cursor()
        cur.execute('DELETE FROM stored_messages WHERE msg_id = ?', (msg_id,))
        self.conn.commit()

    def ensure_chat(self, username: str):
        """Создаёт запись в таблице chats, если её ещё нет."""
        cur = self.conn.cursor()
        cur.execute('''
            INSERT OR IGNORE INTO chats (contact_username, last_message_time, unread_count)
            VALUES (?, ?, 0)
        ''', (username, time.time()))
        self.conn.commit()
