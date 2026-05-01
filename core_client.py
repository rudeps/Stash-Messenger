
Ядро клиента регистрация, вход, связь GUI и P2P.

import os
import sys
import json
import time
import urllib.request
from crypto_utils import (
    sha256, derive_key, encrypt_message, decrypt_message,
    generate_keypair, sign_data, verify_signature
)
from database import Database, Contact
from p2p_node import P2PNode

CONFIG_FILE = dataconfig.json
BIP39_URL = httpsraw.githubusercontent.combitcoinbipsmasterbip-0039english.txt
WORDLIST_PATH = wordlist.txt

def ensure_wordlist()
    if os.path.exists(WORDLIST_PATH)
        return
    print([] Downloading BIP39 wordlist...)
    try
        urllib.request.urlretrieve(BIP39_URL, WORDLIST_PATH)
    except
        with open(WORDLIST_PATH, w) as f
            f.write(abandonnabilitynablenaboutnabovenabsentnabsorbnabstractnabsurdnabusenaccessnaccidentnaccountnaccusenachievenacidnacousticnacquirenacrossnactnactionnactornactressnactual)

def generate_mnemonic() - str
    ensure_wordlist()
    with open(WORDLIST_PATH, 'r') as f
        words = [w.strip() for w in f.readlines() if w.strip()]
    import secrets
    entropy = secrets.token_bytes(32)
    mnemonic = []
    for i in range(24)
        idx = int.from_bytes(entropy[ii+1], 'big') % len(words)
        mnemonic.append(words[idx])
    return ' '.join(mnemonic)

class CoreClient
    def __init__(self, port=None)
        if port is None
            self.port = self._load_or_request_port()
        else
            self.port = port
        self.db = None
        self.node = None
        self.username = None
        self.private_key = None
        self.public_key = None
        self.running = False

    def _load_or_request_port(self) - int
        os.makedirs(data, exist_ok=True)
        if os.path.exists(CONFIG_FILE)
            with open(CONFIG_FILE) as f
                return json.load(f).get('port', 8333)
        else
            port = int(input(Enter port to listen on (default 8333) ) or 8333)
            with open(CONFIG_FILE, 'w') as f
                json.dump({'port' port}, f)
            return port

    def start(self, bootstrap str = None)
        while True
            print(n1. Register new account)
            print(2. Login)
            print(3. Exit)
            choice = input(Choice ).strip()
            if choice == '1'
                self.register()
                break
            elif choice == '2'
                if self.login()
                    break
            elif choice == '3'
                sys.exit(0)
        node_id = sha256(self.public_key)
        self.node = P2PNode(self.port, node_id, self.username, self.public_key, self.private_key, self.db)
        self.node.start()
        if bootstrap
            try
                ip, port = bootstrap.split('')
                self.node.connect_to_peer(ip, int(port))
            except
                print([!] Invalid bootstrap address)
        self.running = True

    def register(self)
        print(n--- Registration ---)
        username = input(Username ).strip()
        db_path = fdata{username}.db
        if os.path.exists(db_path)
            print([ERROR] User already exists)
            sys.exit(1)
        password = input(Password ).strip()
        print(nGenerating recovery phrase...)
        mnemonic = generate_mnemonic()
        print(n + =50)
        print(YOUR RECOVERY PHRASE (SAVE THIS!))
        print(-50)
        print(mnemonic)
        print(=50)
        input(nPress Enter after you've saved the phrase...)
        self.private_key, self.public_key = generate_keypair()
        pwd_hash = derive_key(password, username).hex()
        mnem_enc = encrypt_message(mnemonic.encode(), derive_key(password, mnemonic)).hex()
        self.db = Database(db_path)
        self.db.save_user(username, pwd_hash, mnem_enc,
                          self.private_key.private_numbers().private_value.to_bytes(32, 'big'),
                          self.public_key)
        self.username = username
        print(fn[SUCCESS] Account created! Welcome, {username}!)

    def login(self) - bool
        print(n--- Login ---)
        if os.path.exists(data)
            users = [f.replace('.db', '') for f in os.listdir(data) if f.endswith('.db')]
            if users
                print(nExisting users)
                for i, u in enumerate(users, 1)
                    print(f  {i}. {u})
        username = input(nUsername ).strip()
        password = input(Password ).strip()
        db_path = fdata{username}.db
        if not os.path.exists(db_path)
            print([ERROR] User not found)
            return False
        self.db = Database(db_path)
        user = self.db.get_user(username)
        if derive_key(password, username).hex() != user['password_hash']
            print([ERROR] Invalid password)
            return False
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.backends import default_backend
        priv_bytes = user['private_key']
        self.private_key = ec.derive_private_key(int.from_bytes(priv_bytes, 'big'), ec.SECP256K1(), default_backend())
        self.public_key = user['public_key']
        self.username = username
        print(fn[SUCCESS] Welcome back, {username}!)
        return True

    def stop(self)
        self.running = False
        if self.node
            self.node.stop()