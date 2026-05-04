P2P Decentralized Messenger

A peer-to-peer encrypted messenger with a DHT-based overlay, contact discovery, offline message storage, and a Telegram-style GUI.

Features
- No central server – all communication is peer-to-peer.
- Kademlia DHT for peer and contact discovery.
- End-to-end encryption (ECDH + AES, planned for message payloads).
- Offline messaging – messages are stored on multiple nodes until the recipient comes online.
- Recovery phrase (BIP39-like) for account restoration.
- Telegram-like GUI built with tkinter.

Current Status
Work in progress – the chat list sidebar is not fully functional yet. Contacts may not appear until a message is exchanged manually.

Requirements
- Python 3.9+
- tkinter (usually included with Python)
- cryptography library

Install dependencies: pip install cryptography

Quick Start
Clone the repository and navigate into it: git clone <repo-url> && cd p2p-messenger
Run the client: python client.py
On first run you will be asked for a port (default: 8333), then you can register a new account or log in.
To skip the port prompt: python client.py --port 8333

How to Connect to Another Peer
1. Ensure both peers are on the same network or have public IP addresses and open ports.
2. Start Peer A (the bootstrap node) without the --bootstrap argument: python client.py --port 8333
3. Start Peer B with --bootstrap pointing to Peer A: python client.py --port 8334 --bootstrap 192.168.1.10:8333
4. The two nodes will exchange HELLO messages and populate each other's contact lists.
5. After connecting, you can also use the GUI: Network → Connect to peer… and enter IP:port.
6. To start a chat, click + New Chat, enter the username, and send a message.

GUI Preview
<img width="1858" height="699" alt="image" src="https://github.com/user-attachments/assets/3b1fedac-764a-4161-851e-25898bebb021" />

Troubleshooting
- Chat list empty: known issue, contacts may not appear until a message is exchanged. Workaround: use + New Chat, find the user, and send a message.
- Port already in use: choose a different port with --port.
- Cannot connect to peer: check firewall settings and ensure both nodes use the correct IP address.

Architecture
client.py – entry point, argument parsing.
core_client.py – account management, key derivation, startup menu.
gui.py – Telegram-style UI.
p2p_node.py – Kademlia DHT overlay, message routing, offline storage.
database.py – SQLite tables for users, contacts, messages.
crypto_utils.py – AES, ECDSA, PBKDF2 helpers.

License
MIT
