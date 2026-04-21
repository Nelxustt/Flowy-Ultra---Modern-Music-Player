import os
import sys
import threading
import requests
import sqlite3
from io import BytesIO
from PIL import Image, ImageFilter, ImageDraw
import yt_dlp
import customtkinter as ctk
from plyer import notification

# ── VLC ────────────────────────────────────────────────────────────────────────
vlc_path = r'C:\Program Files\VideoLAN\VLC'
if os.path.exists(vlc_path):
    os.add_dll_directory(vlc_path)
try:
    import vlc
except ImportError:
    print("Error: No se encontró el módulo python-vlc.")

# ── BASE DE DATOS ──────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect("flowy_data.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS favoritos (
            id TEXT PRIMARY KEY,
            titulo TEXT,
            url_web TEXT,
            thumbnail TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ── PALETA SPOTIFY ─────────────────────────────────────────────────────────────
BG_BASE      = "#121212"   # fondo raíz
BG_SIDEBAR   = "#000000"   # sidebar negro puro
BG_CARD      = "#181818"   # tarjetas
BG_HOVER     = "#282828"   # hover
BG_PLAYER    = "#181818"   # barra inferior
ACCENT       = "#1DB954"   # verde Spotify
ACCENT_DARK  = "#158A3E"
TEXT_PRIMARY = "#FFFFFF"
TEXT_SEC     = "#B3B3B3"
TEXT_MUTED   = "#535353"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

# ══════════════════════════════════════════════════════════════════════════════
class FlowyApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Flowy")
        self.geometry("1280x820")
        self.minsize(1000, 700)
        self.configure(fg_color=BG_BASE)

        # Motor VLC
        try:
            self.instance = vlc.Instance("--no-xlib --quiet --no-video")
            self.player   = self.instance.media_player_new()
        except Exception as e:
            print(f"Error VLC: {e}")
            self.player = None

        self.current_track  = None
        self.repro_queue    = []
        self._user_seeking  = False

        self._build_layout()
        self._apply_volume(70)
        self._tick()

    # ── LAYOUT PRINCIPAL ───────────────────────────────────────────────────────
    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()
        self._build_player_bar()

    # ── SIDEBAR ────────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=240, fg_color=BG_SIDEBAR, corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)

        # Logo
        logo = ctk.CTkLabel(sb, text="🎵  Flowy",
                            font=ctk.CTkFont("Helvetica", 26, "bold"),
                            text_color=TEXT_PRIMARY)
        logo.pack(padx=20, pady=(28, 24), anchor="w")

        # Nav buttons
        def nav_btn(parent, icon, label, cmd):
            f = ctk.CTkFrame(parent, fg_color="transparent", cursor="hand2")
            f.pack(fill="x", padx=12, pady=2)
            btn = ctk.CTkButton(f, text=f"  {icon}  {label}",
                                anchor="w",
                                fg_color="transparent",
                                hover_color=BG_HOVER,
                                text_color=TEXT_SEC,
                                font=ctk.CTkFont("Helvetica", 14, "bold"),
                                height=40,
                                corner_radius=6,
                                command=cmd)
            btn.pack(fill="x")
            return btn

        self._btn_search = nav_btn(sb, "🔍", "Buscar",     self.show_search)
        self._btn_favs   = nav_btn(sb, "💚", "Me gusta",   self.show_favorites)

        # Separador
        sep = ctk.CTkFrame(sb, height=1, fg_color=BG_HOVER)
        sep.pack(fill="x", padx=12, pady=16)

        # Cola
        ctk.CTkLabel(sb, text="SIGUIENTE EN COLA",
                     font=ctk.CTkFont("Helvetica", 10, "bold"),
                     text_color=TEXT_MUTED).pack(padx=20, anchor="w")

        self.queue_frame = ctk.CTkScrollableFrame(sb, fg_color="transparent",
                                                   scrollbar_button_color=BG_HOVER)
        self.queue_frame.pack(fill="both", expand=True, padx=8, pady=6)

    # ── MAIN VIEW ──────────────────────────────────────────────────────────────
    def _build_main(self):
        self.main_frame = ctk.CTkFrame(self, fg_color=BG_BASE, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)

        # Barra de búsqueda superior
        top = ctk.CTkFrame(self.main_frame, fg_color=BG_BASE, height=72)
        top.grid(row=0, column=0, sticky="ew", padx=24, pady=(18, 0))
        top.grid_columnconfigure(0, weight=1)

        search_bg = ctk.CTkFrame(top, fg_color=BG_CARD, corner_radius=24, height=44)
        search_bg.grid(row=0, column=0, sticky="ew")
        search_bg.grid_columnconfigure(1, weight=1)
        search_bg.grid_propagate(False)

        ctk.CTkLabel(search_bg, text="🔍", font=ctk.CTkFont("Helvetica", 16),
                     text_color=TEXT_SEC).grid(row=0, column=0, padx=(16, 4), pady=10)

        self.search_entry = ctk.CTkEntry(
            search_bg,
            placeholder_text="¿Qué quieres escuchar?",
            fg_color="transparent",
            border_width=0,
            text_color=TEXT_PRIMARY,
            placeholder_text_color=TEXT_MUTED,
            font=ctk.CTkFont("Helvetica", 14),
            height=44
        )
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=(0, 16))
        self.search_entry.bind("<Return>", lambda e: self._search_thread())

        # Área de resultados
        self.results_scroll = ctk.CTkScrollableFrame(
            self.main_frame, fg_color="transparent",
            scrollbar_button_color=BG_HOVER
        )
        self.results_scroll.grid(row=1, column=0, sticky="nsew", padx=16, pady=(12, 4))

        self._show_welcome()

    # ── BARRA DE PLAYER ────────────────────────────────────────────────────────
    def _build_player_bar(self):
        bar = ctk.CTkFrame(self, height=90, fg_color=BG_PLAYER, corner_radius=0)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        bar.grid_columnconfigure(1, weight=1)
        bar.grid_propagate(False)

        # — Izquierda: portada + info ——
        left = ctk.CTkFrame(bar, fg_color="transparent", width=280)
        left.grid(row=0, column=0, sticky="nsw", padx=16, pady=10)
        left.grid_propagate(False)

        self.cover_label = ctk.CTkLabel(left, text="", width=56, height=56,
                                         fg_color=BG_HOVER, corner_radius=4)
        self.cover_label.pack(side="left")

        info_box = ctk.CTkFrame(left, fg_color="transparent")
        info_box.pack(side="left", padx=12, fill="y", expand=True)

        self.lbl_title = ctk.CTkLabel(info_box, text="—",
                                       font=ctk.CTkFont("Helvetica", 13, "bold"),
                                       text_color=TEXT_PRIMARY, anchor="w", wraplength=160)
        self.lbl_title.pack(anchor="w")

        self.lbl_artist = ctk.CTkLabel(info_box, text="",
                                        font=ctk.CTkFont("Helvetica", 11),
                                        text_color=TEXT_SEC, anchor="w")
        self.lbl_artist.pack(anchor="w", pady=(2, 4))

        # botones acción
        act = ctk.CTkFrame(info_box, fg_color="transparent")
        act.pack(anchor="w")

        self.btn_fav = ctk.CTkButton(act, text="♡", width=28, height=28,
                                      fg_color="transparent", hover_color=BG_HOVER,
                                      text_color=TEXT_SEC,
                                      font=ctk.CTkFont("Helvetica", 16),
                                      corner_radius=14, command=self.toggle_fav)
        self.btn_fav.pack(side="left", padx=(0, 4))

        self.btn_dl = ctk.CTkButton(act, text="⬇", width=28, height=28,
                                     fg_color="transparent", hover_color=BG_HOVER,
                                     text_color=TEXT_SEC,
                                     font=ctk.CTkFont("Helvetica", 14),
                                     corner_radius=14, command=self._download_thread)
        self.btn_dl.pack(side="left")

        # — Centro: controles + progreso ——
        center = ctk.CTkFrame(bar, fg_color="transparent")
        center.grid(row=0, column=1, sticky="nsew", pady=8)
        center.grid_columnconfigure(0, weight=1)

        # Botones de control
        ctrl = ctk.CTkFrame(center, fg_color="transparent")
        ctrl.grid(row=0, column=0)

        def ctrl_btn(parent, symbol, size=18, accent=False, cmd=None):
            color = ACCENT if accent else TEXT_SEC
            b = ctk.CTkButton(parent, text=symbol, width=38, height=38,
                              fg_color="transparent",
                              hover_color=BG_HOVER,
                              text_color=color,
                              font=ctk.CTkFont("Helvetica", size, "bold"),
                              corner_radius=19,
                              command=cmd)
            b.pack(side="left", padx=4)
            return b

        ctrl_btn(ctrl, "⏮", cmd=lambda: None)
        self.btn_play_pause = ctk.CTkButton(
            ctrl, text="▶", width=44, height=44,
            fg_color=TEXT_PRIMARY, hover_color="#e0e0e0",
            text_color=BG_BASE,
            font=ctk.CTkFont("Helvetica", 18, "bold"),
            corner_radius=22,
            command=self._toggle_play
        )
        self.btn_play_pause.pack(side="left", padx=6)
        ctrl_btn(ctrl, "⏭", cmd=self._skip_next)

        # Barra de progreso
        prog_row = ctk.CTkFrame(center, fg_color="transparent")
        prog_row.grid(row=1, column=0, sticky="ew", padx=20, pady=(6, 0))
        prog_row.grid_columnconfigure(1, weight=1)

        self.lbl_current = ctk.CTkLabel(prog_row, text="0:00",
                                         font=ctk.CTkFont("Helvetica", 11),
                                         text_color=TEXT_MUTED, width=36)
        self.lbl_current.grid(row=0, column=0, padx=(0, 8))

        self.progress = ctk.CTkSlider(prog_row, from_=0, to=100,
                                       height=4,
                                       button_color=TEXT_PRIMARY,
                                       button_hover_color=ACCENT,
                                       progress_color=TEXT_PRIMARY,
                                       fg_color=BG_HOVER,
                                       command=self._on_seek)
        self.progress.set(0)
        self.progress.grid(row=0, column=1, sticky="ew")

        self.lbl_total = ctk.CTkLabel(prog_row, text="0:00",
                                       font=ctk.CTkFont("Helvetica", 11),
                                       text_color=TEXT_MUTED, width=36)
        self.lbl_total.grid(row=0, column=2, padx=(8, 0))

        # — Derecha: volumen ——
        right = ctk.CTkFrame(bar, fg_color="transparent", width=200)
        right.grid(row=0, column=2, sticky="nse", padx=20, pady=20)
        right.grid_propagate(False)

        self.lbl_vol_icon = ctk.CTkLabel(right, text="🔉",
                                          font=ctk.CTkFont("Helvetica", 16),
                                          text_color=TEXT_SEC)
        self.lbl_vol_icon.pack(side="left")

        self.vol_slider = ctk.CTkSlider(right, from_=0, to=100, width=100,
                                         height=4,
                                         button_color=TEXT_PRIMARY,
                                         button_hover_color=ACCENT,
                                         progress_color=TEXT_PRIMARY,
                                         fg_color=BG_HOVER,
                                         command=self._apply_volume)
        self.vol_slider.set(70)
        self.vol_slider.pack(side="left", padx=8)

    # ── WELCOME SCREEN ─────────────────────────────────────────────────────────
    def _show_welcome(self):
        for w in self.results_scroll.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.results_scroll,
                     text="Busca tu música favorita 🎶",
                     font=ctk.CTkFont("Helvetica", 22, "bold"),
                     text_color=TEXT_PRIMARY).pack(pady=(40, 8))
        ctk.CTkLabel(self.results_scroll,
                     text="Escribe en la barra de arriba y presiona Enter",
                     font=ctk.CTkFont("Helvetica", 14),
                     text_color=TEXT_SEC).pack()

    # ── NAVIGATION ─────────────────────────────────────────────────────────────
    def show_search(self):
        self.search_entry.master.master.grid()   # asegura visible
        self._show_welcome()

    def show_favorites(self):
        for w in self.results_scroll.winfo_children():
            w.destroy()

        ctk.CTkLabel(self.results_scroll,
                     text="💚  Me gusta",
                     font=ctk.CTkFont("Helvetica", 22, "bold"),
                     text_color=TEXT_PRIMARY).pack(pady=(20, 14), anchor="w", padx=4)

        conn = sqlite3.connect("flowy_data.db")
        rows = conn.cursor().execute("SELECT * FROM favoritos").fetchall()
        conn.close()

        if not rows:
            ctk.CTkLabel(self.results_scroll, text="Aún no tienes canciones guardadas",
                         font=ctk.CTkFont("Helvetica", 14),
                         text_color=TEXT_SEC).pack(pady=20)
            return

        for row in rows:
            v = {'id': row[0], 'title': row[1], 'webpage_url': row[2],
                 'thumbnail': row[3], 'url': row[2]}
            self._make_track_row(v)

    # ── BÚSQUEDA ───────────────────────────────────────────────────────────────
    def _search_thread(self):
        query = self.search_entry.get().strip()
        if not query:
            return
        for w in self.results_scroll.winfo_children():
            w.destroy()

        spin = ctk.CTkLabel(self.results_scroll,
                             text="Buscando  ⏳",
                             font=ctk.CTkFont("Helvetica", 14),
                             text_color=TEXT_SEC)
        spin.pack(pady=30)
        threading.Thread(target=self._do_search, args=(query,), daemon=True).start()

    def _do_search(self, query):
        opts = {'format': 'bestaudio/best', 'quiet': True, 'default_search': 'ytsearch15'}
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(f"ytsearch15:{query}", download=False)
                self.after(0, lambda: self._render_results(info['entries']))
            except Exception as e:
                print(f"Search error: {e}")

    def _render_results(self, entries):
        for w in self.results_scroll.winfo_children():
            w.destroy()

        ctk.CTkLabel(self.results_scroll,
                     text=f"Resultados  ({len(entries)})",
                     font=ctk.CTkFont("Helvetica", 13, "bold"),
                     text_color=TEXT_MUTED).pack(anchor="w", padx=4, pady=(4, 10))

        for entry in entries:
            self._make_track_row(entry)

    # ── FILA DE CANCIÓN ────────────────────────────────────────────────────────
    def _make_track_row(self, video):
        row = ctk.CTkFrame(self.results_scroll, fg_color="transparent",
                           cursor="hand2", corner_radius=6)
        row.pack(fill="x", pady=1, padx=2)

        # Hover effect
        row.bind("<Enter>", lambda e: row.configure(fg_color=BG_HOVER))
        row.bind("<Leave>", lambda e: row.configure(fg_color="transparent"))

        # Número / ícono
        num = ctk.CTkLabel(row, text="♪", width=32,
                            font=ctk.CTkFont("Helvetica", 14),
                            text_color=TEXT_MUTED)
        num.pack(side="left", padx=(10, 6))

        # Texto
        txt = ctk.CTkFrame(row, fg_color="transparent")
        txt.pack(side="left", fill="x", expand=True, pady=8)

        title = video.get('title', 'Sin título')
        ctk.CTkLabel(txt, text=title[:60],
                     font=ctk.CTkFont("Helvetica", 13, "bold"),
                     text_color=TEXT_PRIMARY,
                     anchor="w").pack(anchor="w")

        duration = video.get('duration', 0)
        dur_str  = f"{int(duration)//60}:{int(duration)%60:02d}" if duration else "—"
        ctk.CTkLabel(txt, text=dur_str,
                     font=ctk.CTkFont("Helvetica", 11),
                     text_color=TEXT_MUTED, anchor="w").pack(anchor="w")

        # Botón "+ Cola"
        btn_q = ctk.CTkButton(row, text="+ Cola", width=62, height=28,
                               fg_color="transparent",
                               border_width=1,
                               border_color=BG_HOVER,
                               hover_color=BG_HOVER,
                               text_color=TEXT_SEC,
                               font=ctk.CTkFont("Helvetica", 11),
                               corner_radius=14,
                               command=lambda v=video: self._add_to_queue(v))
        btn_q.pack(side="right", padx=12)

        # Click para reproducir
        for widget in (row, txt, num):
            widget.bind("<Button-1>", lambda e, v=video: self._play(v))
        for lbl in txt.winfo_children():
            lbl.bind("<Button-1>", lambda e, v=video: self._play(v))

    # ── REPRODUCCIÓN ──────────────────────────────────────────────────────────
    def _play(self, video_data):
        threading.Thread(target=self._do_play, args=(video_data,), daemon=True).start()

    def _do_play(self, video_data):
        try:
            if self.player and self.player.is_playing():
                self.player.stop()

            url = video_data.get('url') or video_data.get('webpage_url', '')
            if "youtube.com" in url or "youtu.be" in url:
                with yt_dlp.YoutubeDL({'format': 'bestaudio/best', 'quiet': True}) as ydl:
                    info = ydl.extract_info(url, download=False)
                    url  = info['url']

            self.current_track = {
                'id':      video_data.get('id', ''),
                'titulo':  video_data.get('title', 'Desconocido'),
                'web_url': video_data.get('webpage_url', video_data.get('url', '')),
                'thumb':   video_data.get('thumbnail', '')
            }

            media = self.instance.media_new(url)
            self.player.set_media(media)
            self.player.play()

            self.after(0, self._refresh_player_ui)
            self._notify(self.current_track['titulo'])

            threading.Thread(target=self._load_cover,
                             args=(self.current_track['thumb'],), daemon=True).start()
        except Exception as e:
            print(f"Play error: {e}")

    def _refresh_player_ui(self):
        if not self.current_track:
            return
        self.lbl_title.configure(text=self.current_track['titulo'][:40])
        self.lbl_artist.configure(text="YouTube Music")
        self.btn_play_pause.configure(text="⏸")

        # Estado de favorito
        conn = sqlite3.connect("flowy_data.db")
        is_fav = conn.cursor().execute(
            "SELECT id FROM favoritos WHERE id=?", (self.current_track['id'],)
        ).fetchone()
        conn.close()
        self.btn_fav.configure(text="♥" if is_fav else "♡",
                                text_color=ACCENT if is_fav else TEXT_SEC)

    def _toggle_play(self):
        if not self.player:
            return
        if self.player.is_playing():
            self.player.pause()
            self.btn_play_pause.configure(text="▶")
        else:
            self.player.play()
            self.btn_play_pause.configure(text="⏸")

    def _skip_next(self):
        if self.repro_queue:
            nxt = self.repro_queue.pop(0)
            self._update_queue_ui()
            self._play(nxt)
        else:
            if self.player:
                self.player.stop()
            self.lbl_title.configure(text="—")
            self.btn_play_pause.configure(text="▶")

    def _add_to_queue(self, video):
        self.repro_queue.append(video)
        self._update_queue_ui()

    def _update_queue_ui(self):
        for w in self.queue_frame.winfo_children():
            w.destroy()
        for i, v in enumerate(self.repro_queue):
            f = ctk.CTkFrame(self.queue_frame, fg_color="transparent")
            f.pack(fill="x", pady=1)
            ctk.CTkLabel(f, text=f"{i+1}",
                         font=ctk.CTkFont("Helvetica", 10),
                         text_color=TEXT_MUTED, width=18).pack(side="left")
            ctk.CTkLabel(f, text=v['title'][:22],
                         font=ctk.CTkFont("Helvetica", 11),
                         text_color=TEXT_SEC, anchor="w").pack(side="left")

    # ── FAVORITOS ──────────────────────────────────────────────────────────────
    def toggle_fav(self):
        if not self.current_track:
            return
        conn   = sqlite3.connect("flowy_data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM favoritos WHERE id=?", (self.current_track['id'],))
        if cursor.fetchone():
            cursor.execute("DELETE FROM favoritos WHERE id=?", (self.current_track['id'],))
            self.btn_fav.configure(text="♡", text_color=TEXT_SEC)
        else:
            cursor.execute("INSERT INTO favoritos VALUES (?,?,?,?)",
                           (self.current_track['id'], self.current_track['titulo'],
                            self.current_track['web_url'], self.current_track['thumb']))
            self.btn_fav.configure(text="♥", text_color=ACCENT)
        conn.commit()
        conn.close()

    # ── DESCARGA ───────────────────────────────────────────────────────────────
    def _download_thread(self):
        if self.current_track:
            threading.Thread(target=self._do_download, daemon=True).start()

    def _do_download(self):
        self.btn_dl.configure(state="disabled", text="⏳")
        os.makedirs("descargas", exist_ok=True)
        opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'descargas/{self.current_track["titulo"]}.%(ext)s',
            'postprocessors': [{'key': 'FFmpegExtractAudio',
                                'preferredcodec': 'mp3',
                                'preferredquality': '192'}]
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([self.current_track['web_url']])
        except Exception as e:
            print(f"Download error: {e}")
        self.btn_dl.configure(state="normal", text="⬇")

    # ── PROGRESO Y VOLUMEN ─────────────────────────────────────────────────────
    def _on_seek(self, val):
        if self.player:
            self.player.set_position(val / 100.0)

    def _apply_volume(self, val):
        v = int(val)
        if self.player:
            self.player.audio_set_volume(v)
        # ícono dinámico
        if v == 0:
            icon = "🔇"
        elif v < 30:
            icon = "🔈"
        elif v < 75:
            icon = "🔉"
        else:
            icon = "🔊"
        self.lbl_vol_icon.configure(text=icon)

    def _fmt(self, ms):
        s = max(0, int(ms / 1000))
        return f"{s // 60}:{s % 60:02d}"

    def _tick(self):
        if self.player and self.player.is_playing():
            pos   = self.player.get_position()
            ms_c  = self.player.get_time()
            ms_t  = self.player.get_length()
            self.progress.set(pos * 100)
            self.lbl_current.configure(text=self._fmt(ms_c))
            if ms_t > 0:
                self.lbl_total.configure(text=self._fmt(ms_t))

        if self.player and self.player.get_state() == vlc.State.Ended:
            self._skip_next()

        self.after(1000, self._tick)

    # ── PORTADA ────────────────────────────────────────────────────────────────
    def _load_cover(self, url):
        try:
            res = requests.get(url, timeout=5)
            img = Image.open(BytesIO(res.content)).resize((56, 56), Image.Resampling.LANCZOS)
            # Esquinas redondeadas
            mask = Image.new("L", (56, 56), 0)
            draw = ImageDraw.Draw(mask)
            draw.rounded_rectangle([0, 0, 55, 55], radius=6, fill=255)
            img.putalpha(mask)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(56, 56))
            self.after(0, lambda: self.cover_label.configure(image=ctk_img, text=""))
        except Exception as e:
            print(f"Cover error: {e}")

    # ── NOTIFICACIONES ─────────────────────────────────────────────────────────
    def _notify(self, titulo):
        try:
            notification.notify(
                title="Flowy: Reproduciendo ahora",
                message=titulo,
                app_name="Flowy Music",
                timeout=4
            )
        except Exception as e:
            print(f"Notify error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = FlowyApp()
    app.mainloop()