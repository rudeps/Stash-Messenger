Stash — P2P Messenger: Technical Description

1. CURRENT STATE (Working Python Prototype)
Fully decentralized messenger. No phone, no email, no central server. Username auth.
- P2P: Custom UDP protocol, Kademlia DHT with k-buckets. FIND_NODE, FIND_VALUE, STORE.
- Crypto: secp256k1 keys, AES-256-CTR messages, PBKDF2 key derivation (100k iterations).
- Hybrid encryption: asymmetric for key exchange, symmetric for messages. Private keys never leave device.
- Offline: Encrypted messages stored on K closest DHT nodes, TTL 48h, auto-retrieved on login.
- Recovery: BIP39 mnemonic (24 words).
- GUI: Telegram-style, tkinter. Chat list, search, bubbles, timestamps, online/offline status.
- DB: SQLite (users, contacts, messages, offline relay).
- Code: ~1200 lines, 5 modules. All from scratch, no messenger frameworks.

2. PLANNED (Grant Scope)
- Replace raw UDP with external decentralized storage API. No IP exposure between peers. Direct P2P fallback stays. Messenger network remains serverless — zero central infrastructure for message routing.
- Stash utility token. 1% burn fee per tx. Non-custodial wallets. P2P exchange with bank link verification, no KYC. Token server is centralized; messenger protocol is untouched if it goes down.
- Security audit of all crypto.
- C++ migration start.

3. KEY DESIGN PROPERTY
Token layer and messenger layer are architecturally isolated. Kill all token servers — messaging, file transfer, calls still work over P2P. Kill all P2P infrastructure — nothing works, by definition. There is no central point of failure for communication.

Source: GPLv3. Built alone. 14 years old.
