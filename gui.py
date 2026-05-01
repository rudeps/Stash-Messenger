"""
Графический интерфейс мессенджера.
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, font
from datetime import datetime
import time
import threading
import re

from core_client import CoreClient
from database import Message

class TelegramStyleGUI:
    def __init__(self, core: CoreClient):
        self.core = core
        self.root = tk.Tk()
        self.root.title(f"P2P Messenger - {core.username}")
        self.root.geometry("900x650")
        self.root.minsize(700, 500)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Цветовая схема
        self.colors = {
            'bg_main': '#f0f2f5',
            'bg_sidebar': '#ffffff',
            'bg_chat': '#e5ddd5',
            'bubble_out': '#e1ffc7',
            'bubble_in': '#ffffff',
            'text_primary': '#000000',
            'text_secondary': '#707579',
            'accent': '#3390ec',
            'online': '#4caf50',
            'offline': '#9e9e9e',
            'border': '#d1d1d1'
        }

        self.current_chat = None
        self.pending_chat = None
        self.contacts_frame = None
        self.chat_header_frame = None
        self.chat_messages_frame = None
        self.message_input = None
        self.status_var = tk.StringVar()
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_contacts)

        self.setup_menu()
        self.setup_ui()
        self.refresh_contacts()
        self.setup_callbacks()
        self.root.after(5000, self.periodic_refresh)

    def setup_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        network_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Network", menu=network_menu)
        network_menu.add_command(label="Connect to peer...", command=self.connect_dialog)
        network_menu.add_command(label="Refresh contacts", command=self.refresh_contacts)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=lambda: messagebox.showinfo("About", "P2P Decentralized Messenger"))

    def connect_dialog(self):
        addr = simpledialog.askstring("Connect to peer", "Enter IP:port:", parent=self.root)
        if addr:
            try:
                ip, port = addr.split(':')
                self.core.node.connect_to_peer(ip, int(port))
                self.status_var.set(f"Connected to {addr}")
            except:
                messagebox.showerror("Error", "Invalid address format. Use ip:port")

    def setup_ui(self):
        self.root.configure(bg=self.colors['bg_main'])

        # Главный горизонтальный контейнер
        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        # ---------- Левая панель (список контактов) ----------
        left_frame = tk.Frame(main_pane, bg=self.colors['bg_sidebar'], width=280)
        main_pane.add(left_frame, weight=0)
        left_frame.pack_propagate(False)

        # Заголовок левой панели
        header_left = tk.Frame(left_frame, bg=self.colors['bg_sidebar'], height=60)
        header_left.pack(fill=tk.X, pady=10, padx=10)
        tk.Label(header_left, text="Chats", font=('Segoe UI', 14, 'bold'),
                 bg=self.colors['bg_sidebar'], fg=self.colors['text_primary']).pack(side=tk.LEFT)

        # Поле поиска
        search_frame = tk.Frame(left_frame, bg=self.colors['bg_sidebar'])
        search_frame.pack(fill=tk.X, padx=10, pady=(0,10))
        search_entry = tk.Entry(search_frame, textvariable=self.search_var,
                                font=('Segoe UI', 10), relief=tk.FLAT, bg='#f5f5f5')
        search_entry.pack(fill=tk.X, ipady=8)
        search_entry.insert(0, "Search")
        search_entry.bind("<FocusIn>", lambda e: search_entry.delete(0, tk.END) if search_entry.get() == "Search" else None)
        search_entry.bind("<FocusOut>", lambda e: search_entry.insert(0, "Search") if not search_entry.get() else None)

        # Список контактов (Canvas + Scrollbar)
        self.contacts_canvas = tk.Canvas(left_frame, bg=self.colors['bg_sidebar'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.contacts_canvas.yview)
        self.contacts_frame = tk.Frame(self.contacts_canvas, bg=self.colors['bg_sidebar'])
        self.contacts_frame.bind("<Configure>", lambda e: self.contacts_canvas.configure(scrollregion=self.contacts_canvas.bbox("all")))
        self.contacts_canvas.create_window((0,0), window=self.contacts_frame, anchor="nw")
        self.contacts_canvas.configure(yscrollcommand=scrollbar.set)

        self.contacts_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Кнопка "New Chat"
        btn_new = tk.Button(left_frame, text="+ New Chat", font=('Segoe UI', 10, 'bold'),
                            bg=self.colors['accent'], fg='white', relief=tk.FLAT,
                            command=self.new_chat_dialog, cursor='hand2')
        btn_new.pack(fill=tk.X, padx=10, pady=10, ipady=8)

        # ---------- Правая панель (чат) ----------
        right_frame = tk.Frame(main_pane, bg=self.colors['bg_chat'])
        main_pane.add(right_frame, weight=3)

        # Шапка чата
        self.chat_header_frame = tk.Frame(right_frame, bg=self.colors['bg_sidebar'], height=60)
        self.chat_header_frame.pack(fill=tk.X, padx=1, pady=1)
        self.chat_header_frame.pack_propagate(False)

        self.chat_avatar_label = tk.Label(self.chat_header_frame, text="👤", font=('Segoe UI', 18),
                                          bg=self.colors['bg_sidebar'], fg=self.colors['accent'])
        self.chat_avatar_label.pack(side=tk.LEFT, padx=15, pady=10)

        self.chat_info_frame = tk.Frame(self.chat_header_frame, bg=self.colors['bg_sidebar'])
        self.chat_info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=10)
        self.chat_name_label = tk.Label(self.chat_info_frame, text="Select a chat",
                                        font=('Segoe UI', 12, 'bold'), bg=self.colors['bg_sidebar'])
        self.chat_name_label.pack(anchor='w')
        self.chat_status_label = tk.Label(self.chat_info_frame, text="",
                                          font=('Segoe UI', 9), bg=self.colors['bg_sidebar'],
                                          fg=self.colors['text_secondary'])
        self.chat_status_label.pack(anchor='w')

        # Область сообщений (Canvas с прокруткой)
        self.messages_canvas = tk.Canvas(right_frame, bg=self.colors['bg_chat'], highlightthickness=0)
        messages_scroll = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.messages_canvas.yview)
        self.chat_messages_frame = tk.Frame(self.messages_canvas, bg=self.colors['bg_chat'])
        self.chat_messages_frame.bind("<Configure>", self._on_frame_configure)
        self.messages_canvas.create_window((0,0), window=self.chat_messages_frame, anchor="nw", tags="frame")
        self.messages_canvas.configure(yscrollcommand=messages_scroll.set)

        self.messages_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=(10,0))
        messages_scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=(10,0))

        # Поле ввода
        input_frame = tk.Frame(right_frame, bg=self.colors['bg_sidebar'], height=50)
        input_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=10)
        input_frame.pack_propagate(False)

        self.message_input = tk.Text(input_frame, font=('Segoe UI', 11), height=1, width=40,
                                     relief=tk.FLAT, bg='#ffffff', wrap=tk.WORD)
        self.message_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10,5), pady=5)
        self.message_input.bind('<Return>', self.send_message_event)
        self.message_input.bind('<Shift-Return>', lambda e: None)
        self.message_input.config(state='disabled')

        send_btn = tk.Button(input_frame, text="➤", font=('Segoe UI', 14), bg=self.colors['accent'],
                             fg='white', relief=tk.FLAT, width=3, command=self.send_message,
                             cursor='hand2')
        send_btn.pack(side=tk.RIGHT, padx=(5,10), pady=5)

        # Статус бар
        status_bar = tk.Label(self.root, textvariable=self.status_var, anchor='w',
                              bg=self.colors['bg_main'], fg=self.colors['text_secondary'])
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _on_frame_configure(self, event):
        self.messages_canvas.configure(scrollregion=self.messages_canvas.bbox("all"))

    def setup_callbacks(self):
        def callback(event_type, data):
            if event_type == 'message':
                self.root.after(0, self.handle_incoming_message, data)
            elif event_type == 'contact_found':
                self.root.after(0, self.handle_contact_found, data)
        self.core.node.add_callback(callback)

    def handle_incoming_message(self, msg: Message):
        self.refresh_contacts()
        if self.current_chat == msg.sender_username:
            self.display_message(msg)
        else:
            self.status_var.set(f"New message from {msg.sender_username}")

    def handle_contact_found(self, username):
        self.refresh_contacts()
        self.status_var.set(f"Found user: {username}")
        if self.pending_chat == username:
            self.open_chat(username)
            self.pending_chat = None

    def periodic_refresh(self):
        self.refresh_contacts()
        if self.current_chat:
            self.update_chat_status()
        self.root.after(5000, self.periodic_refresh)

    def refresh_contacts(self):
        if not self.contacts_frame:
            return
        # Очищаем фрейм
        for widget in self.contacts_frame.winfo_children():
            widget.destroy()

        chats = self.core.db.get_chats()
        all_contacts = {}
        for username, last_time, unread in chats:
            contact = self.core.db.get_contact(username)
            all_contacts[username] = (last_time, unread, contact)

        # Фильтрация по поиску
        search_term = self.search_var.get().lower()
        if search_term and search_term != "search":
            filtered = {u: v for u, v in all_contacts.items() if search_term in u.lower()}
        else:
            filtered = all_contacts

        for username, (last_time, unread, contact) in filtered.items():
            self._create_contact_row(username, last_time, unread, contact)

    def _create_contact_row(self, username, last_time, unread, contact):
        row = tk.Frame(self.contacts_frame, bg=self.colors['bg_sidebar'], height=65)
        row.pack(fill=tk.X, padx=5, pady=2)
        row.pack_propagate(False)

        # Аватар
        avatar = tk.Label(row, text=username[0].upper(), font=('Segoe UI', 12, 'bold'),
                          bg=self.colors['accent'], fg='white', width=4, height=2, relief=tk.FLAT)
        avatar.pack(side=tk.LEFT, padx=10, pady=10)

        info_frame = tk.Frame(row, bg=self.colors['bg_sidebar'])
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=8)

        name_label = tk.Label(info_frame, text=username, font=('Segoe UI', 11, 'bold'),
                              bg=self.colors['bg_sidebar'], anchor='w')
        name_label.pack(fill=tk.X)

        # Последнее сообщение (можно улучшить)
        last_msg_label = tk.Label(info_frame, text="Tap to open chat", font=('Segoe UI', 9),
                                  bg=self.colors['bg_sidebar'], fg=self.colors['text_secondary'], anchor='w')
        last_msg_label.pack(fill=tk.X)

        right_frame = tk.Frame(row, bg=self.colors['bg_sidebar'])
        right_frame.pack(side=tk.RIGHT, padx=10, pady=8)

        time_str = datetime.fromtimestamp(last_time).strftime('%H:%M')
        time_label = tk.Label(right_frame, text=time_str, font=('Segoe UI', 9),
                              bg=self.colors['bg_sidebar'], fg=self.colors['text_secondary'])
        time_label.pack(anchor='e')

        if unread > 0:
            badge = tk.Label(right_frame, text=str(unread), font=('Segoe UI', 9, 'bold'),
                             bg=self.colors['accent'], fg='white', width=2, relief=tk.FLAT)
            badge.pack(pady=(5,0))

        # Привязка клика для открытия чата
        for widget in (row, avatar, name_label, last_msg_label, time_label):
            widget.bind("<Button-1>", lambda e, u=username: self.open_chat(u))
            widget.bind("<Enter>", lambda e, r=row: r.configure(bg='#f5f5f5'))
            widget.bind("<Leave>", lambda e, r=row: r.configure(bg=self.colors['bg_sidebar']))

    def filter_contacts(self, *args):
        self.refresh_contacts()

    def open_chat(self, username):
        self.current_chat = username
        self.chat_name_label.config(text=username)
        self.update_chat_status()

        # Очистка области сообщений
        for widget in self.chat_messages_frame.winfo_children():
            widget.destroy()

        # Загрузка истории
        messages = self.core.db.get_chat_history(username)
        for msg in messages:
            self.display_message(msg)

        self.message_input.config(state='normal')
        self.message_input.focus()

        # Прокрутка вниз
        self.messages_canvas.after(100, self._scroll_to_bottom)

    def update_chat_status(self):
        if not self.current_chat:
            return
        contact = self.core.db.get_contact(self.current_chat)
        if contact and (time.time() - contact.last_seen) < 300:
            self.chat_status_label.config(text="online", fg=self.colors['online'])
        else:
            self.chat_status_label.config(text="last seen recently", fg=self.colors['offline'])

    def display_message(self, msg: Message):
        is_outgoing = (msg.sender_username == self.core.username)
        bg_color = self.colors['bubble_out'] if is_outgoing else self.colors['bubble_in']
        anchor = 'e' if is_outgoing else 'w'

        bubble_frame = tk.Frame(self.chat_messages_frame, bg=self.colors['bg_chat'])
        bubble_frame.pack(fill=tk.X, padx=10, pady=5, anchor=anchor)

        bubble = tk.Frame(bubble_frame, bg=bg_color, relief=tk.FLAT, bd=0)
        bubble.pack(side=tk.RIGHT if is_outgoing else tk.LEFT, padx=20, pady=2)

        msg_text = tk.Label(bubble, text=msg.content, font=('Segoe UI', 11),
                            bg=bg_color, fg=self.colors['text_primary'],
                            wraplength=400, justify=tk.LEFT)
        msg_text.pack(padx=12, pady=8, anchor='w')

        time_str = datetime.fromtimestamp(msg.timestamp).strftime('%H:%M')
        time_label = tk.Label(bubble, text=time_str, font=('Segoe UI', 8),
                              bg=bg_color, fg=self.colors['text_secondary'])
        time_label.pack(padx=12, pady=(0,5), anchor='e')

        self.messages_canvas.after(100, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        self.messages_canvas.yview_moveto(1.0)

    def send_message_event(self, event=None):
        if not event.state & 0x1:
            self.send_message()
            return 'break'

    def send_message(self):
        if not self.current_chat:
            return
        content = self.message_input.get("1.0", tk.END).strip()
        if not content:
            return
        self.message_input.delete("1.0", tk.END)

        contact = self.core.db.get_contact(self.current_chat)
        if not contact:
            self.status_var.set(f"Searching for {self.current_chat}...")
            self.core.node.find_user(self.current_chat)
            self.pending_chat = self.current_chat
            messagebox.showinfo("Info", f"User {self.current_chat} not in contacts. Searching... Please try again in a moment.")
            return

        success = self.core.node.send_message(self.current_chat, content)
        if success:
            msg = Message(
                msg_id='local',
                sender_username=self.core.username,
                recipient_username=self.current_chat,
                content=content,
                timestamp=time.time(),
                signature=b''
            )
            self.display_message(msg)
            self.refresh_contacts()
        else:
            messagebox.showerror("Error", "Failed to send message.")

    def new_chat_dialog(self):
        username = simpledialog.askstring("New Chat", "Enter username:", parent=self.root)
        if not username:
            return
        username = username.strip()
        if username == self.core.username:
            messagebox.showwarning("Warning", "Cannot chat with yourself.")
            return
        contact = self.core.db.get_contact(username)
        if not contact:
            self.status_var.set(f"Searching for {username}...")
            self.core.node.find_user(username)
            self.pending_chat = username
            messagebox.showinfo("Info", f"Searching for {username}. The chat will open once found.")
            self.root.after(2000, self.check_pending_chat)
        else:
            self.open_chat(username)

    def check_pending_chat(self):
        if self.pending_chat:
            username = self.pending_chat
            contact = self.core.db.get_contact(username)
            if contact:
                self.open_chat(username)
                self.pending_chat = None
            else:
                self.root.after(2000, self.check_pending_chat)

    def on_close(self):
        self.core.stop()
        self.root.destroy()