import speech_recognition as sr
import tkinter as tk
from tkinter import ttk
import re
import threading
import queue
import winsound


class DartsGep:
    def __init__(self):
        self.score = 501
        # Előző állások a visszavonáshoz
        self.history = []
        # UI elemek (később inicializáljuk)
        self.root = None
        self.score_label = None
        self.checkout_label = None
        self.history_list = None
        self.history_scrollbar = None
        self.last_change_index = None
        # Nyílszámlálás
        self.start_turn_score = self.score
        self.darts_used_total = 0
        self.darts_in_turn = 0  # 0–3, aktuális körben elhasznált nyilak
        self.darts_turn_label = None
        self.darts_total_label = None
        # Kommunikáció a hangfelismerő szál és a UI között
        self.command_queue = queue.Queue()
        self.running = True

    def speak(self, text):
        # Jelenleg nem beszélünk ki, csak a konzolra írunk
        print(f"Darts Segéd: {text}")

    def play_success_sound(self):
        """
        Sikeres dobás esetén lejátszott hang.
        Először egy Windows rendszerhangot próbálunk (általában hangosabb),
        ha ez nem sikerül, akkor egy hosszabb, jól hallható Beep-et használunk.
        """
        try:
            # Rendszer sikerhang (általában a hangszórón szól)
            winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
        except Exception:
            try:
                # Tartalék: hosszabb Beep
                winsound.Beep(1000, 300)
            except Exception:
                pass

    def play_error_sound(self):
        """
        Sikertelen / félresikerült felismerés esetén lejátszott hang.
        Jelenleg NINCS hang visszajelzés hibára – szándékosan üres.
        """
        return

    # ---------- UI ----------
    def init_ui(self):
        self.root = tk.Tk()
        self.root.title("Darts Segéd")
        # 1920x1080-ra optimalizálva
        self.root.geometry("1920x1080")

        # Nagy pontszám kijelzés (1920x1080-hoz igazítva)
        self.score_label = ttk.Label(self.root, text=str(self.score), font=("Segoe UI", 120, "bold"))
        self.score_label.pack(pady=(40, 10))

        # Nyilak kijelzése (aktuális kör + összes)
        darts_frame = ttk.Frame(self.root)
        darts_frame.pack(pady=(0, 20))

        self.darts_turn_label = ttk.Label(darts_frame, text="", font=("Segoe UI", 20, "bold"))
        self.darts_turn_label.pack(side=tk.LEFT, padx=20)

        self.darts_total_label = ttk.Label(darts_frame, text="", font=("Segoe UI", 20))
        self.darts_total_label.pack(side=tk.LEFT, padx=20)

        # Kiszálló kijelzés (ha van javaslat) – közepes méretben
        self.checkout_label = ttk.Label(self.root, text="Kiszálló: -", font=("Segoe UI", 32, "bold"), foreground="#006400")
        self.checkout_label.pack(pady=(0, 30))

        # History címke
        history_label = ttk.Label(self.root, text="Ponttörténet:", font=("Segoe UI", 18, "bold"))
        history_label.pack(pady=(10, 0))

        # History keret + görgetős lista
        history_frame = ttk.Frame(self.root)
        history_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=20)

        self.history_list = tk.Listbox(history_frame, height=20, font=("Consolas", 16))
        self.history_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.history_scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=self.history_list.yview)
        self.history_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.history_list.config(yscrollcommand=self.history_scrollbar.set)

        # Bezárás gomb
        close_btn = ttk.Button(self.root, text="Bezárás", command=self.close_app)
        close_btn.pack(pady=10)

        # Kezdeti állapot a history-ban
        self.add_history_entry("Kezdő pontszám", self.score, highlight=True)
        # Nyilak UI induló értékekkel
        self.update_darts_ui()

    def update_score_ui(self):
        if self.score_label is not None:
            self.score_label.config(text=str(self.score))

    def update_darts_ui(self):
        """Aktuális kör nyilai és összes nyíl frissítése a UI-n."""
        if self.darts_turn_label is not None:
            self.darts_turn_label.config(text=f"Kör nyilai: {self.darts_in_turn} / 3")
        if self.darts_total_label is not None:
            self.darts_total_label.config(text=f"Összes nyíl: {self.darts_used_total}")

    def update_checkout_ui(self, tipp: str | None):
        if self.checkout_label is None:
            return
        if tipp is None or tipp == "Nincs fix javaslat":
            self.checkout_label.config(text="Kiszálló: -")
        else:
            self.checkout_label.config(text=f"Kiszálló: {tipp}")

    def add_history_entry(self, leiras: str, ertek: int, highlight: bool = False):
        """
        Új sor a history listában.
        A legújabb kerüljön a lista TETEJÉRE (fordított sorrend).
        Ha highlight=True, akkor azt a sort kiemeljük.
        """
        if self.history_list is None:
            return

        sor = f"{leiras}: {ertek}"
        # Új elem a lista tetejére
        self.history_list.insert(0, sor)

        # Görgessünk automatikusan a tetejére
        self.history_list.yview_moveto(0)

        if highlight:
            # Előző kiemelések törlése (egyszerű, de biztos módszer)
            size = self.history_list.size()
            for i in range(size):
                self.history_list.itemconfig(i, bg="white", fg="black")
            # Az első (legújabb) elemet emeljük ki
            self.history_list.itemconfig(0, bg="#ffd966", fg="black")  # halvány sárga

    def close_app(self):
        # UI bezárása + játék leállítása
        self.running = False
        if self.root is not None:
            self.root.destroy()

    def get_checkout(self, s):
        # PDC / általánosan használt kiszálló-táblázat (170-től lefelé)
        # Formátum: a pontszám -> ajánlott dobássorozat
        checkouts = {
            170: "T20, T20, Bull",
            167: "T20, T19, Bull",
            164: "T20, T18, Bull",
            161: "T20, T17, Bull",
            160: "T20, T20, D20",
            158: "T20, T20, D19",
            157: "T20, T19, D20",
            156: "T20, T20, D18",
            155: "T20, T19, D19",
            154: "T20, T18, D20",
            153: "T20, T19, D18",
            152: "T20, T20, D16",
            151: "T20, T17, D20",
            150: "T20, T18, D18",
            149: "T20, T19, D16",
            148: "T20, T16, D20",
            147: "T20, T17, D18",
            146: "T20, T18, D16",
            145: "T20, T15, D20",
            144: "T20, T20, D12",
            143: "T20, T17, D16",
            142: "T20, T14, D20",
            141: "T20, T19, D12",
            140: "T20, T16, D16",
            139: "T20, T13, D20",
            138: "T20, T18, D12",
            137: "T20, T15, D16",
            136: "T20, T20, D8",
            135: "T20, T17, D12",
            134: "T20, T14, D16",
            133: "T20, T19, D8",
            132: "T20, T16, D12",
            131: "T20, T13, D16",
            130: "T20, T18, D8",
            129: "T19, T16, D12",
            128: "T18, T14, D16",
            127: "T20, T17, D8",
            126: "T19, T19, D6",
            125: "25, T20, D20",
            124: "T20, T16, D8",
            123: "T19, T16, D9",
            122: "T18, T18, D7",
            121: "T20, T11, D14",
            120: "T20, 20, D20",
            119: "T19, T10, D16",
            118: "T20, 18, D20",
            117: "T20, 17, D20",
            116: "T20, 16, D20",
            115: "T20, 15, D20",
            114: "T20, 14, D20",
            113: "T20, 13, D20",
            112: "T20, 12, D20",
            111: "T20, 11, D20",
            110: "T20, 10, D20",
            109: "T20, 9, D20",
            108: "T20, 16, D16",
            107: "T19, 18, D16",
            106: "T20, 10, D18",
            105: "T20, 13, D16",
            104: "T18, 18, D16",
            103: "T20, 11, D16",
            102: "T20, 10, D16",
            101: "T17, 10, D20",
            100: "T20, D20",
            99: "T19, 10, D16",
            98: "T20, D19",
            97: "T19, D20",
            96: "T20, D18",
            95: "T19, D19",
            94: "T18, D20",
            93: "T19, D18",
            92: "T20, D16",
            91: "T17, D20",
            90: "T18, D18",
            89: "T19, D16",
            88: "T16, D20",
            87: "T17, D18",
            86: "T18, D16",
            85: "T15, D20",
            84: "T20, D12",
            83: "T17, D16",
            82: "Bull, D16",
            81: "T19, D12",
            80: "T20, D10",
            79: "T13, D20",
            78: "T18, D12",
            77: "T15, D16",
            76: "T20, D8",
            75: "T17, D12",
            74: "T14, D16",
            73: "T19, D8",
            72: "T16, D12",
            71: "T13, D16",
            70: "T18, D8",
            69: "T19, D6",
            68: "T20, D4",
            67: "T17, D8",
            66: "T10, D18",
            65: "T11, D16",
            64: "T16, D8",
            63: "T13, D12",
            62: "T10, D16",
            61: "T15, D8",
            60: "20, D20",
            59: "19, D20",
            58: "18, D20",
            57: "17, D20",
            56: "16, D20",
            55: "15, D20",
            54: "14, D20",
            53: "13, D20",
            52: "12, D20",
            51: "11, D20",
            50: "Bull",
            49: "9, D20",
            48: "16, D16",
            47: "15, D16",
            46: "14, D16",
            45: "13, D16",
            44: "12, D16",
            43: "11, D16",
            42: "10, D16",
            41: "9, D16",
            40: "D20",
            39: "7, D16",
            38: "D19",
            37: "5, D16",
            36: "D18",
            35: "3, D16",
            34: "D17",
            33: "1, D16",
            32: "D16",
            31: "15, D8",
            30: "D15",
            29: "13, D8",
            28: "D14",
            27: "11, D8",
            26: "D13",
            25: "9, D8",
            24: "D12",
            23: "7, D8",
            22: "D11",
            21: "5, D8",
            20: "D10",
            19: "3, D8",
            18: "D9",
            17: "1, D8",
            16: "D8",
            15: "7, D4",
            14: "D7",
            13: "5, D4",
            12: "D6",
            11: "3, D4",
            10: "D5",
            9: "1, D4",
            8: "D4",
            7: "3, D2",
            6: "D3",
            5: "1, D2",
            4: "D2",
            3: "1, D1",
            2: "D1",
        }
        return checkouts.get(s, "Nincs fix javaslat")

    def interpret_command(self, parancs_kis: str, command_raw: str):
        """
        Felismert szövegből visszaad egy dobásértéket vagy speciális parancsot.
        """
        # STOP parancs
        if parancs_kis in ["stop", "állj", "kilepes", "kilépés", "exit"]:
            return "STOP"

        # VISSZAVONÁS parancs
        if parancs_kis in ["visszavonás", "visszavonas", "vissza", "mégse", "megse", "undo"]:
            return "UNDO"

        # ÚJRA (játék újraindítása)
        if parancs_kis in ["újra", "ujra", "restart", "újrakezdés", "ujrakezdes"]:
            return "RESET"

        # Ha "tripla" / "dupla" összeragad valamivel (pl. "triplanyolc", "tripla20")
        if parancs_kis.startswith("tripla") and " " not in parancs_kis[:8]:
            parancs_kis = parancs_kis.replace("tripla", "tripla ", 1)
        if parancs_kis.startswith("dupla") and " " not in parancs_kis[:7]:
            parancs_kis = paranc_kis.replace("dupla", "dupla ", 1)

        # DUPLA / TRIPLA kezelése (pl. "dupla húsz", "tripla tizenöt")
        dupla_tripla_ertek = self.parse_dupla_tripla(parancs_kis)
        if dupla_tripla_ertek is not None:
            return dupla_tripla_ertek

        # Magyar számnevek kezelése (pl. "hat", "húsz")
        szam_szo = self.magyar_szam_szo_to_int(parancs_kis)
        if szam_szo is not None:
            return szam_szo

        # Ha több szám is van a szövegben (pl. "18 20"), vegyük az UTOLSÓT
        nums = re.findall(r"\d+", parancs_kis)
        if len(nums) >= 1:
            return int(nums[-1])

        # Ha a motor számot mond, de raggal (pl. "6-os", "6 os", "6 pont")
        m = re.match(r"^\s*(\d+)", parancs_kis)
        if m:
            return int(m.group(1))

        # Ha a motor mégis tiszta számként adta vissza (pl. "60")
        try:
            return int(command_raw)
        except ValueError:
            # Ha nem tiszta számot mondtál be
            return None

    def listen_score(self):
        """
        Egyszeri hallgatás – jelenleg a listen_loop használja a logikát,
        de ez megmarad tartaléknak / hibakereséshez.
        """
        r = sr.Recognizer()
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=0.5)
            print("Hallgatlak...")
            try:
                audio = r.listen(source, timeout=3, phrase_time_limit=3)
                # Magyar nyelvű felismerés
                command = r.recognize_google(audio, language="hu-HU")
                print(f"Felismert szöveg: {command}")
                parancs_kis = command.strip().lower()
                return self.interpret_command(parancs_kis, command)
            except Exception as e:
                print(f"Hiba a felismerés során: {e}")
                return None

    def magyar_szam_szo_to_int(self, szoveg: str):
        """
        Egyszerű magyar számnév -> int átalakítás.
        Nem teljes, de a darts szempontjából hasznosabb gyakori értékeket (0–180) próbáljuk lefedni.
        """
        szoveg = szoveg.strip().lower()

        alapok = {
            "nulla": 0, "semmi": 0,
            "egy": 1, "egyik": 1,
            "kettő": 2, "ketto": 2, "két": 2, "ket": 2,
            "három": 3, "harom": 3,
            "négy": 4, "negy": 4,
            "öt": 5, "ot": 5,
            "hat": 6,
            "hét": 7, "het": 7,
            "nyolc": 8,
            "kilenc": 9,
            "tíz": 10, "tiz": 10,
            "tizenegy": 11, "tizenketto": 12, "tizenkettő": 12, "tizenharom": 13, "tizenhárom": 13,
        }

        tizesek = {
            "tíz": 10, "tiz": 10,
            "húsz": 20, "husz": 20,
            "harminc": 30,
            "negyven": 40,
            "ötven": 50, "otven": 50,
            "hatvan": 60,
            "hetven": 70,
            "nyolcvan": 80,
            "kilencven": 90,
            "száz": 100, "szaz": 100,
        }

        # Egyszerű, egy szóból álló számnév (pl. "hatvan")
        if szoveg in alapok:
            return alapok[szoveg]
        if szoveg in tizesek:
            return tizesek[szoveg]

        # Összetett (pl. "hatvan egy", "száz húsz")
        szavak = szoveg.split()
        if len(szavak) == 2:
            elso, masodik = szavak
            ertek = 0
            if elso in tizesek:
                ertek += tizesek[elso]
            elif elso in alapok:
                ertek += alapok[elso]
            else:
                return None

            if masodik in alapok:
                ertek += alapok[masodik]
                return ertek

        return None

    def parse_dupla_tripla(self, szoveg: str):
        """
        Kezeli a "dupla X" / "tripla X" formákat.
        Visszatér a megfelelő pontszámmal, vagy None, ha nem sikerült értelmezni.
        """
        szoveg = szoveg.strip().lower()
        szavak = szoveg.split()
        if len(szavak) < 2:
            return None

        elso = szavak[0]
        tobbi = " ".join(szavak[1:]).strip()

        szorzo = None
        if elso in ["dupla", "double", "dupla-"]:
            szorzo = 2
        elif elso in ["tripla", "triple", "tripla-"]:
            szorzo = 3

        if szorzo is None:
            return None

        # Próbáljuk először magyar számnévként értelmezni a maradékot
        alap = self.magyar_szam_szo_to_int(tobbi)
        if alap is None:
            # Ha nem sikerül, próbáljuk meg sima számmá alakítani
            try:
                alap = int(tobbi)
            except ValueError:
                return None

        return alap * szorzo

    def process_commands(self):
        """
        A felismert dobásokat a fő (UI) szálban dolgozzuk fel,
        így az ablak nem fagy le a hangfelismerés miatt.
        """
        # Több parancsot is lekezelünk egyszerre, ha a queue-ban várnak
        while not self.command_queue.empty() and self.score > 1 and self.running:
            dobas = self.command_queue.get_nowait()

            # Felismerési hiba / timeout jelzése
            if dobas == "ERROR":
                self.play_error_sound()
                continue

            # STOP → csendben kilépünk
            if dobas == "STOP":
                self.running = False
                if self.root is not None and self.root.winfo_exists():
                    self.root.destroy()
                return

            # ÚJRAINDÍTÁS (RESET): vissza 501-re, history + nyilak törlése, UI frissítése
            if dobas == "RESET":
                self.score = 501
                self.history.clear()
                self.darts_used_total = 0
                self.darts_in_turn = 0
                # History lista vizuális törlése
                if self.history_list is not None:
                    self.history_list.delete(0, tk.END)
                # Kezdő állapot újra
                self.update_score_ui()
                self.update_checkout_ui(None)
                self.update_darts_ui()
                self.add_history_entry("Kezdő pontszám", self.score, highlight=True)
                continue

            # VISSZAVONÁS
            if dobas == "UNDO":
                if self.history:
                    elozo_allas = self.history.pop()
                    self.score = elozo_allas
                    if self.darts_in_turn > 0:
                        self.darts_in_turn = self.darts_in_turn - 1
                    else:
                        self.darts_in_turn = 2
                self.darts_used_total = self.darts_used_total - 1
                self.update_darts_ui()
                self.update_score_ui()
                self.add_history_entry("Visszavonás", self.score, highlight=True)
                # Ha nincs history, egyszerűen nem csinálunk semmit
                continue

            # Ha nem értette pontosan – marad a jelenlegi állás
            if dobas is None:
                # Nincs változás, nincs hang
                continue

            # Besokallás ellenőrzése (0 alá esés is)
            remaining = self.score - dobas
            if dobas > self.score or remaining == 1 or remaining < 0:
                # Besokallás: a teljes kör 3 elhasznált nyílnak számít
                darts_to_add = max(0, 3 - self.darts_in_turn)
                self.darts_used_total += darts_to_add
                self.darts_in_turn = 0
                self.score = self.start_turn_score
                self.update_score_ui()
                self.update_darts_ui()
                self.play_success_sound()
                self.add_history_entry(f"Besokallás (dobás: {dobas})", self.score, highlight=True)
                continue

            # Sikeres dobás: nyilak növelése
            self.darts_in_turn += 1
            self.darts_used_total += 1

            # Visszavonás támogatás: elmentjük az előző állást
            self.history.append(self.score)
            self.add_history_entry(f"Dobás -{dobas}", remaining, highlight=False)
            self.score = remaining

            # UI frissítése az új állásra
            self.update_score_ui()
            self.update_darts_ui()
            # Sikeres levonás hang
            self.play_success_sound()
            if self.score == 0:
                self.add_history_entry("Játék vége", self.score, highlight=True)
                self.running = False
                #if self.root is not None and self.root.winfo_exists():
                #    self.root.destroy()
                return

            self.add_history_entry("Új állás", self.score, highlight=True)

            # Kiszálló figyelmeztetés + UI frissítés
            if self.score <= 170:
                tipp = self.get_checkout(self.score)
                if tipp != "Nincs fix javaslat":
                    self.update_checkout_ui(tipp)
                else:
                    self.update_checkout_ui(None)
            else:
                # Nem vagy kiszálló zónában
                self.update_checkout_ui(None)

            # Ha letelt a 3 nyíl és még nincs kiszálló, új kört kezdünk
            if self.score > 0 and self.darts_in_turn >= 3:
                self.start_turn_score = self.score
                self.darts_in_turn = 0
                self.update_darts_ui()

        # Ha még fut a játék és az ablak él, ütemezzük újra magunkat
        if self.running and self.root is not None and self.root.winfo_exists() and self.score > 1:
            self.root.after(50, self.process_commands)

    def listen_loop(self):
        """
        Külön szálon futó végtelen ciklus, ami folyamatosan hallgatja a dobásokat,
        és a command_queue-ba rakja az eredményt.
        """
        r = sr.Recognizer()
        with sr.Microphone() as source:
            # Csak egyszer mérjük fel a háttérzajt, hogy ne legyen minden dobás között fél másodperc szünet
            r.adjust_for_ambient_noise(source, duration=0.5)
            while self.running and self.score > 1:
                print("Hallgatlak...")
                try:
                    audio = r.listen(source, timeout=3, phrase_time_limit=3)
                except Exception as e:
                    # Timeout vagy egyéb hiba – dobás nélkül megyünk tovább
                    print(f"Hiba a hallgatás során: {e}")
                    self.command_queue.put("ERROR")
                    continue

                try:
                    command = r.recognize_google(audio, language="hu-HU")
                    print(f"Felismert szöveg: {command}")
                    parancs_kis = command.strip().lower()
                    dobas = self.interpret_command(parancs_kis, command)
                    self.command_queue.put(dobas)
                    if dobas == "STOP":
                        break
                except Exception as e:
                    print(f"Hiba a felismerés során: {e}")
                    self.command_queue.put("ERROR")

    def jatek(self):
        # UI inicializálása
        self.init_ui()
        # Nyilak alaphelyzetbe (biztonság kedvéért)
        self.darts_used_total = 0
        self.darts_in_turn = 0
        self.update_darts_ui()

        # Hangfelismerő szál indítása
        listener_thread = threading.Thread(target=self.listen_loop, daemon=True)
        listener_thread.start()

        # Parancsok feldolgozásának elindítása a fő (UI) szálban
        self.root.after(50, self.process_commands)

        # Tkinter fő ciklus
        self.root.mainloop()

if __name__ == "__main__":
    DartsGep().jatek()