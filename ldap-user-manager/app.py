import base64
import hashlib
import json
import os
import secrets
import string
import ssl
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk

try:
    from ldap3 import Server, Connection, ALL, SUBTREE, BASE, MODIFY_ADD, Tls
except Exception:
    Server = Connection = ALL = SUBTREE = BASE = MODIFY_ADD = Tls = None

APP_NAME = "OpenLDAP User Manager"
APP_VERSION = "2.0.0"

COLORS = {
    "bg": "#0B0F14",
    "sidebar": "#10161F",
    "surface": "#141B25",
    "surface2": "#192230",
    "surface3": "#1F2A3A",
    "border": "#273446",
    "text": "#F3F7FC",
    "muted": "#93A3B8",
    "accent": "#4C8DFF",
    "accent_hover": "#6AA0FF",
    "green": "#35C48D",
    "yellow": "#E6AE52",
    "red": "#F06A74",
    "input": "#0F1620",
}

DEFAULTS = {
    "ldap_host": "",
    "ldap_port": 636,
    "use_ssl": True,
    "start_tls": False,
    "verify_tls": True,
    "bind_dn": "",
    "base_dn": "",
    "users_ou": "ou=users",
    "groups_ou": "ou=groups",
    "mail_domain": "",
    "home_prefix": "/home",
    "login_shell": "/bin/bash",
    "uid_start": 10000,
    "gid_mode": "same_as_uid",
    "fixed_gid": 10000,
    "window_geometry": "1180x760",
}

def app_dir():
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent

def config_path():
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA", Path.home())) / "OpenLDAPUserManager"
    else:
        root = Path.home() / ".config" / "openldap-user-manager"
    root.mkdir(parents=True, exist_ok=True)
    return root / "config.json"

def load_profile():
    for name in ("defaults.json", "alea-defaults.json"):
        p = app_dir() / name
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
    return {}

def join_dn(*parts):
    return ",".join(str(x).strip().strip(",") for x in parts if str(x).strip().strip(","))

def escape_filter(value):
    return value.replace("\\", r"\5c").replace("*", r"\2a").replace("(", r"\28").replace(")", r"\29").replace("\x00", r"\00")

def make_ssha(password):
    salt = os.urandom(8)
    digest = hashlib.sha1(password.encode("utf-8") + salt).digest()
    return "{SSHA}" + base64.b64encode(digest + salt).decode("ascii")

def ldif_line(key, value):
    s = str(value)
    unsafe = (not s.isascii() or s.startswith((" ", ":", "<")) or s.endswith(" ") or "\n" in s or "\r" in s)
    if unsafe:
        return f"{key}:: {base64.b64encode(s.encode('utf-8')).decode('ascii')}"
    return f"{key}: {s}"

def to_ldif(dn, attrs):
    lines = [ldif_line("dn", dn)]
    for key, value in attrs.items():
        vals = value if isinstance(value, (list, tuple)) else [value]
        lines.extend(ldif_line(key, v) for v in vals)
    return "\n".join(lines) + "\n"

class HoverButton(tk.Button):
    def __init__(self, master, text, command=None, kind="secondary", **kw):
        pal = {
            "primary": (COLORS["accent"], COLORS["accent_hover"], "#FFFFFF"),
            "secondary": (COLORS["surface3"], "#2A3950", COLORS["text"]),
            "ghost": (COLORS["surface"], COLORS["surface2"], COLORS["muted"]),
        }
        bg, hover, fg = pal[kind]
        super().__init__(master, text=text, command=command, bg=bg, fg=fg, activebackground=hover,
                         activeforeground=fg, relief="flat", bd=0, highlightthickness=0,
                         font=("Segoe UI", 10, "bold" if kind == "primary" else "normal"),
                         cursor="hand2", padx=14, pady=9, **kw)
        self._bg, self._hover = bg, hover
        self.bind("<Enter>", lambda e: self.configure(bg=self._hover))
        self.bind("<Leave>", lambda e: self.configure(bg=self._bg))

class Pill(tk.Label):
    def __init__(self, master, text="Не проверено", tone="neutral"):
        super().__init__(master, font=("Segoe UI", 9, "bold"), padx=10, pady=5, bd=0)
        self.set(text, tone)
    def set(self, text, tone="neutral"):
        tones = {
            "neutral": (COLORS["surface3"], COLORS["muted"]),
            "good": ("#123A31", "#67E2B7"),
            "warn": ("#41331D", "#F1C46C"),
            "bad": ("#462329", "#FF919A"),
        }
        bg, fg = tones[tone]
        self.configure(text=text, bg=bg, fg=fg)

class Field(tk.Frame):
    def __init__(self, master, label, variable, readonly=False, secret=False, helper=None):
        super().__init__(master, bg=COLORS["surface"])
        tk.Label(self, text=label, bg=COLORS["surface"], fg=COLORS["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0,5))
        self.entry = tk.Entry(self, textvariable=variable, bg=COLORS["input"], fg=COLORS["text"],
                              insertbackground=COLORS["text"], relief="flat", bd=0, highlightthickness=1,
                              highlightbackground=COLORS["border"], highlightcolor=COLORS["accent"],
                              readonlybackground=COLORS["input"], font=("Segoe UI",10), show="•" if secret else "")
        self.entry.pack(fill="x", ipady=8)
        if readonly:
            self.entry.configure(state="readonly")
        if helper:
            tk.Label(self, text=helper, bg=COLORS["surface"], fg=COLORS["muted"], font=("Segoe UI",8)).pack(anchor="w", pady=(4,0))

class ScrollFrame(tk.Frame):
    def __init__(self, master, bg):
        super().__init__(master, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, bd=0, highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.win = self.canvas.create_window((0,0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.win, width=e.width))

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.configure(bg=COLORS["bg"])
        self.minsize(1040,680)
        self.cfg = DEFAULTS.copy(); self.cfg.update(load_profile()); self._load_config()
        self.geometry(self.cfg.get("window_geometry","1180x760"))
        self.busy=False; self.group_rows=[]; self.log_lines=[]; self.current_password_hash=None
        self.var_login=tk.StringVar(); self.var_email=tk.StringVar(); self.var_dn=tk.StringVar()
        self.var_uid=tk.StringVar(value="AUTO"); self.var_gid=tk.StringVar(value="AUTO")
        self.var_password=tk.StringVar(); self.var_show_password=tk.BooleanVar(False); self.var_group_search=tk.StringVar()
        self._style(); self._build(); self.show_page("create")
        self.var_login.trace_add("write", lambda *_: self._derived())
        self.var_group_search.trace_add("write", lambda *_: self._filter_groups())
        self._derived(); self._log("Приложение запущено")
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _style(self):
        s=ttk.Style(self)
        try:s.theme_use("clam")
        except:pass
        s.configure("Vertical.TScrollbar", background=COLORS["surface3"], troughcolor=COLORS["surface"], bordercolor=COLORS["surface"], arrowcolor=COLORS["muted"])

    def _load_config(self):
        p=config_path()
        if p.exists():
            try:self.cfg.update(json.loads(p.read_text(encoding="utf-8")))
            except:pass

    def _save_config(self):
        self.cfg["window_geometry"]=self.geometry()
        config_path().write_text(json.dumps(self.cfg,ensure_ascii=False,indent=2),encoding="utf-8")

    def _build(self):
        shell=tk.Frame(self,bg=COLORS["bg"]); shell.pack(fill="both",expand=True)
        shell.grid_columnconfigure(1,weight=1); shell.grid_rowconfigure(0,weight=1)
        self.sidebar=tk.Frame(shell,bg=COLORS["sidebar"],width=235); self.sidebar.grid(row=0,column=0,sticky="nsew"); self.sidebar.grid_propagate(False)
        brand=tk.Frame(self.sidebar,bg=COLORS["sidebar"]); brand.pack(fill="x",padx=20,pady=(24,28))
        logo=tk.Canvas(brand,width=36,height=36,bg=COLORS["sidebar"],highlightthickness=0); logo.pack(side="left")
        logo.create_oval(3,3,33,33,fill=COLORS["accent"],outline=""); logo.create_text(18,18,text="L",fill="white",font=("Segoe UI",15,"bold"))
        btxt=tk.Frame(brand,bg=COLORS["sidebar"]); btxt.pack(side="left",padx=(10,0))
        tk.Label(btxt,text="LDAP Manager",bg=COLORS["sidebar"],fg=COLORS["text"],font=("Segoe UI",12,"bold")).pack(anchor="w")
        tk.Label(btxt,text=f"v{APP_VERSION}",bg=COLORS["sidebar"],fg=COLORS["muted"],font=("Segoe UI",8)).pack(anchor="w")
        self.nav={}
        for key,text in [("create","＋   Новый пользователь"),("settings","⚙   Настройки LDAP"),("logs","≡   Журнал операций")]:
            b=tk.Button(self.sidebar,text=text,command=lambda k=key:self.show_page(k),anchor="w",bg=COLORS["sidebar"],fg=COLORS["muted"],
                        activebackground=COLORS["surface2"],activeforeground=COLORS["text"],relief="flat",bd=0,cursor="hand2",font=("Segoe UI",10),padx=18,pady=12)
            b.pack(fill="x",padx=12,pady=2); self.nav[key]=b
        foot=tk.Frame(self.sidebar,bg=COLORS["sidebar"]); foot.pack(side="bottom",fill="x",padx=18,pady=18)
        tk.Label(foot,text="LDAP STATUS",bg=COLORS["sidebar"],fg=COLORS["muted"],font=("Segoe UI",8,"bold")).pack(anchor="w",pady=(0,7))
        self.side_status=Pill(foot); self.side_status.pack(anchor="w")
        self.main=tk.Frame(shell,bg=COLORS["bg"]); self.main.grid(row=0,column=1,sticky="nsew"); self.main.grid_columnconfigure(0,weight=1); self.main.grid_rowconfigure(1,weight=1)
        head=tk.Frame(self.main,bg=COLORS["bg"]); head.grid(row=0,column=0,sticky="ew",padx=28,pady=(18,0)); head.grid_columnconfigure(0,weight=1)
        self.title_lbl=tk.Label(head,text="",bg=COLORS["bg"],fg=COLORS["text"],font=("Segoe UI",19,"bold")); self.title_lbl.grid(row=0,column=0,sticky="w")
        self.sub_lbl=tk.Label(head,text="",bg=COLORS["bg"],fg=COLORS["muted"],font=("Segoe UI",9)); self.sub_lbl.grid(row=1,column=0,sticky="w",pady=(3,0))
        self.head_status=Pill(head); self.head_status.grid(row=0,column=1,rowspan=2,sticky="e")
        self.content=tk.Frame(self.main,bg=COLORS["bg"]); self.content.grid(row=1,column=0,sticky="nsew",padx=28,pady=(10,24)); self.content.grid_rowconfigure(0,weight=1); self.content.grid_columnconfigure(0,weight=1)
        self.pages={"create":self._create_page(),"settings":self._settings_page(),"logs":self._logs_page()}

    def _card(self,parent,title,subtitle=None):
        c=tk.Frame(parent,bg=COLORS["surface"],highlightthickness=1,highlightbackground=COLORS["border"])
        h=tk.Frame(c,bg=COLORS["surface"]); h.pack(fill="x",padx=18,pady=(16,10))
        tk.Label(h,text=title,bg=COLORS["surface"],fg=COLORS["text"],font=("Segoe UI",11,"bold")).pack(anchor="w")
        if subtitle: tk.Label(h,text=subtitle,bg=COLORS["surface"],fg=COLORS["muted"],font=("Segoe UI",8)).pack(anchor="w",pady=(3,0))
        return c

    def _create_page(self):
        p=tk.Frame(self.content,bg=COLORS["bg"]); p.grid_columnconfigure(0,weight=3); p.grid_columnconfigure(1,weight=2); p.grid_rowconfigure(0,weight=1)
        l=tk.Frame(p,bg=COLORS["bg"]); r=tk.Frame(p,bg=COLORS["bg"]); l.grid(row=0,column=0,sticky="nsew",padx=(0,8)); r.grid(row=0,column=1,sticky="nsew",padx=(8,0))
        c=self._card(l,"Параметры учётной записи","Почта и DN формируются автоматически из логина"); c.pack(fill="x")
        f=tk.Frame(c,bg=COLORS["surface"]); f.pack(fill="x",padx=18,pady=(0,18)); f.grid_columnconfigure(0,weight=1); f.grid_columnconfigure(1,weight=1)
        Field(f,"Логин",self.var_login,helper="Например: i.ivanov").grid(row=0,column=0,sticky="ew",padx=(0,8),pady=6)
        Field(f,"E-mail",self.var_email,readonly=True).grid(row=0,column=1,sticky="ew",padx=(8,0),pady=6)
        Field(f,"Distinguished Name (DN)",self.var_dn,readonly=True).grid(row=1,column=0,columnspan=2,sticky="ew",pady=6)
        Field(f,"uidNumber",self.var_uid,readonly=True).grid(row=2,column=0,sticky="ew",padx=(0,8),pady=6)
        Field(f,"gidNumber",self.var_gid,readonly=True).grid(row=2,column=1,sticky="ew",padx=(8,0),pady=6)
        pc=self._card(l,"Первоначальный пароль","Генерируется локально и не сохраняется в настройках"); pc.pack(fill="x",pady=(16,0))
        pf=tk.Frame(pc,bg=COLORS["surface"]); pf.pack(fill="x",padx=18,pady=(0,18)); pf.grid_columnconfigure(0,weight=1)
        self.pw=tk.Entry(pf,textvariable=self.var_password,show="•",bg=COLORS["input"],fg=COLORS["text"],insertbackground=COLORS["text"],relief="flat",bd=0,highlightthickness=1,highlightbackground=COLORS["border"],highlightcolor=COLORS["accent"],font=("Consolas",11))
        self.pw.grid(row=0,column=0,sticky="ew",ipady=8)
        HoverButton(pf,"Сгенерировать",self.generate_password).grid(row=0,column=1,padx=(8,0)); HoverButton(pf,"Копировать",self.copy_password).grid(row=0,column=2,padx=(8,0))
        tk.Checkbutton(pf,text="Показать",variable=self.var_show_password,command=self.toggle_password,bg=COLORS["surface"],fg=COLORS["muted"],activebackground=COLORS["surface"],activeforeground=COLORS["text"],selectcolor=COLORS["input"],bd=0).grid(row=1,column=0,sticky="w",pady=(8,0))
        ac=self._card(l,"Проверка и создание"); ac.pack(fill="x",pady=(16,0))
        af=tk.Frame(ac,bg=COLORS["surface"]); af.pack(fill="x",padx=18,pady=(0,18))
        for i in range(3):af.grid_columnconfigure(i,weight=1)
        HoverButton(af,"Проверить (Dry Run)",self.dry_run).grid(row=0,column=0,sticky="ew",padx=(0,5))
        HoverButton(af,"Предпросмотр LDIF",self.preview_ldif).grid(row=0,column=1,sticky="ew",padx=5)
        HoverButton(af,"Сохранить LDIF",self.save_ldif).grid(row=0,column=2,sticky="ew",padx=(5,0))
        HoverButton(af,"Создать пользователя",self.create_user,"primary").grid(row=1,column=0,columnspan=3,sticky="ew",pady=(10,0))
        self.inline=tk.Label(af,text="Сначала выполните Dry Run",bg=COLORS["surface"],fg=COLORS["muted"],font=("Segoe UI",9)); self.inline.grid(row=2,column=0,columnspan=3,sticky="w",pady=(10,0))
        gc=self._card(r,"Группы","Выберите группы для нового пользователя"); gc.pack(fill="both",expand=True)
        tb=tk.Frame(gc,bg=COLORS["surface"]); tb.pack(fill="x",padx=16,pady=(0,10)); tb.grid_columnconfigure(0,weight=1)
        tk.Entry(tb,textvariable=self.var_group_search,bg=COLORS["input"],fg=COLORS["text"],insertbackground=COLORS["text"],relief="flat",bd=0,highlightthickness=1,highlightbackground=COLORS["border"],highlightcolor=COLORS["accent"],font=("Segoe UI",9)).grid(row=0,column=0,sticky="ew",ipady=7)
        HoverButton(tb,"Обновить",self.load_groups).grid(row=0,column=1,padx=(8,0))
        self.group_scroll=ScrollFrame(gc,COLORS["surface"]); self.group_scroll.pack(fill="both",expand=True,padx=12,pady=(0,10))
        tk.Label(self.group_scroll.inner,text="Нажмите «Обновить», чтобы загрузить группы из LDAP",bg=COLORS["surface"],fg=COLORS["muted"],font=("Segoe UI",9),wraplength=320,justify="center").pack(pady=60,padx=20)
        return p

    def _settings_page(self):
        p=tk.Frame(self.content,bg=COLORS["bg"]); s=ScrollFrame(p,COLORS["bg"]); s.pack(fill="both",expand=True); par=s.inner
        c=self._card(par,"Подключение к LDAP","Bind password используется только в памяти и не сохраняется"); c.pack(fill="x",pady=(0,16))
        f=tk.Frame(c,bg=COLORS["surface"]); f.pack(fill="x",padx=18,pady=(0,18)); f.grid_columnconfigure(0,weight=1); f.grid_columnconfigure(1,weight=1)
        self.set_vars={k:tk.StringVar(value=str(self.cfg.get(k,""))) for k in ["ldap_host","ldap_port","bind_dn","base_dn","users_ou","groups_ou","mail_domain","home_prefix","login_shell","uid_start","fixed_gid"]}
        self.bind_password_var=tk.StringVar(); self.use_ssl_var=tk.BooleanVar(value=self.cfg.get("use_ssl",True)); self.start_tls_var=tk.BooleanVar(value=self.cfg.get("start_tls",False)); self.verify_tls_var=tk.BooleanVar(value=self.cfg.get("verify_tls",True)); self.gid_mode_var=tk.StringVar(value=self.cfg.get("gid_mode","same_as_uid"))
        specs=[("LDAP сервер","ldap_host",0,0),("Порт","ldap_port",0,1),("Bind DN","bind_dn",1,0),("Bind password",None,1,1),("Base DN","base_dn",2,0),("Users OU","users_ou",2,1),("Groups OU","groups_ou",3,0),("Домен почты после @","mail_domain",3,1)]
        for label,key,row,col in specs:
            var=self.bind_password_var if key is None else self.set_vars[key]
            Field(f,label,var,secret=(key is None)).grid(row=row,column=col,sticky="ew",padx=(0 if col==0 else 8,8 if col==0 else 0),pady=6)
        flags=tk.Frame(c,bg=COLORS["surface"]); flags.pack(fill="x",padx=18,pady=(0,18))
        for text,var in [("LDAPS (SSL)",self.use_ssl_var),("StartTLS",self.start_tls_var),("Проверять TLS-сертификат",self.verify_tls_var)]:
            tk.Checkbutton(flags,text=text,variable=var,bg=COLORS["surface"],fg=COLORS["text"],activebackground=COLORS["surface"],activeforeground=COLORS["text"],selectcolor=COLORS["input"],bd=0).pack(side="left",padx=(0,18))
        sc=self._card(par,"Схема создаваемого пользователя"); sc.pack(fill="x",pady=(0,16))
        sf=tk.Frame(sc,bg=COLORS["surface"]); sf.pack(fill="x",padx=18,pady=(0,18)); sf.grid_columnconfigure(0,weight=1); sf.grid_columnconfigure(1,weight=1)
        for i,(label,key) in enumerate([("Префикс homeDirectory","home_prefix"),("loginShell","login_shell"),("Минимальный uidNumber","uid_start"),("Фиксированный gidNumber","fixed_gid")]):
            Field(sf,label,self.set_vars[key]).grid(row=i//2,column=i%2,sticky="ew",padx=(0 if i%2==0 else 8,8 if i%2==0 else 0),pady=6)
        gm=tk.Frame(sc,bg=COLORS["surface"]); gm.pack(fill="x",padx=18,pady=(0,18))
        tk.Label(gm,text="gidNumber",bg=COLORS["surface"],fg=COLORS["muted"],font=("Segoe UI",9,"bold")).pack(side="left",padx=(0,12))
        for t,v in [("равен uidNumber","same_as_uid"),("фиксированный","fixed")]:
            tk.Radiobutton(gm,text=t,variable=self.gid_mode_var,value=v,bg=COLORS["surface"],fg=COLORS["text"],activebackground=COLORS["surface"],activeforeground=COLORS["text"],selectcolor=COLORS["input"],bd=0).pack(side="left",padx=(0,16))
        b=tk.Frame(par,bg=COLORS["bg"]); b.pack(fill="x",pady=(0,18))
        HoverButton(b,"Сохранить настройки",self.save_settings,"primary").pack(side="left")
        HoverButton(b,"Проверить подключение",self.test_connection).pack(side="left",padx=(10,0))
        return p

    def _logs_page(self):
        p=tk.Frame(self.content,bg=COLORS["bg"]); c=self._card(p,"Журнал операций","Пароли в журнал не записываются"); c.pack(fill="both",expand=True)
        bar=tk.Frame(c,bg=COLORS["surface"]); bar.pack(fill="x",padx=16,pady=(0,10))
        HoverButton(bar,"Очистить",self.clear_log).pack(side="right"); HoverButton(bar,"Сохранить в файл",self.export_log).pack(side="right",padx=(0,8))
        self.log_text=tk.Text(c,bg=COLORS["input"],fg="#CFD9E8",insertbackground=COLORS["text"],relief="flat",bd=0,highlightthickness=1,highlightbackground=COLORS["border"],font=("Consolas",9),wrap="word")
        self.log_text.pack(fill="both",expand=True,padx=16,pady=(0,16)); self.log_text.configure(state="disabled")
        return p

    def show_page(self,key):
        names={"create":("Новый пользователь","Создание учётной записи OpenLDAP с проверкой перед записью"),"settings":("Настройки LDAP","Подключение, структура каталога и шаблоны"),"logs":("Журнал операций","Диагностика подключений и выполненных изменений")}
        for k,p in self.pages.items(): p.grid_forget(); self.nav[k].configure(bg=COLORS["sidebar"],fg=COLORS["muted"])
        self.pages[key].grid(row=0,column=0,sticky="nsew"); self.nav[key].configure(bg=COLORS["surface2"],fg=COLORS["text"])
        self.title_lbl.configure(text=names[key][0]); self.sub_lbl.configure(text=names[key][1])

    def _derived(self):
        login=self.var_login.get().strip(); dom=self.cfg.get("mail_domain","").strip()
        self.var_email.set(f"{login}@{dom}" if login and dom else ""); self.var_dn.set(self.user_dn(login) if login else "")
        self.var_uid.set("AUTO"); self.var_gid.set("AUTO"); self.current_password_hash=None
        if hasattr(self,"inline"): self.inline.configure(text="Сначала выполните Dry Run",fg=COLORS["muted"])

    def user_base(self): return join_dn(self.cfg.get("users_ou",""),self.cfg.get("base_dn",""))
    def groups_base(self): return join_dn(self.cfg.get("groups_ou",""),self.cfg.get("base_dn",""))
    def user_dn(self,login): return join_dn(f"cn={login}",self.cfg.get("users_ou",""),self.cfg.get("base_dn",""))

    def _settings_from_ui(self):
        if not hasattr(self,"set_vars"): return
        d={k:v.get().strip() for k,v in self.set_vars.items()}
        for k in ("ldap_port","uid_start","fixed_gid"): d[k]=int(d[k])
        d.update(use_ssl=self.use_ssl_var.get(),start_tls=self.start_tls_var.get(),verify_tls=self.verify_tls_var.get(),gid_mode=self.gid_mode_var.get())
        self.cfg.update(d)

    def save_settings(self):
        try:self._settings_from_ui(); self._save_config(); self._derived(); self._log("Настройки сохранены"); messagebox.showinfo(APP_NAME,"Настройки сохранены.\nBind password не сохранялся.")
        except Exception as e: messagebox.showerror(APP_NAME,str(e))

    def _connect(self):
        if Server is None: raise RuntimeError("В сборке отсутствует ldap3")
        host=self.cfg.get("ldap_host","").strip()
        if not host: raise ValueError("Укажите LDAP сервер в настройках")
        validate=ssl.CERT_REQUIRED if self.cfg.get("verify_tls",True) else ssl.CERT_NONE
        tls=Tls(validate=validate)
        server=Server(host,port=int(self.cfg.get("ldap_port",636)),use_ssl=bool(self.cfg.get("use_ssl",True)),tls=tls,get_info=ALL)
        conn=Connection(server,user=self.cfg.get("bind_dn","").strip() or None,password=getattr(self,"_worker_bind_password","") or None,auto_bind=False,raise_exceptions=False)
        if self.cfg.get("start_tls") and not self.cfg.get("use_ssl"):
            if not conn.open(): raise RuntimeError(f"Не удалось открыть соединение: {conn.result}")
            if not conn.start_tls(): raise RuntimeError(f"StartTLS: {conn.result}")
        if not conn.bind(): raise RuntimeError(f"LDAP Bind не выполнен: {conn.result}")
        return conn

    def _status(self,text,tone): self.head_status.set(text,tone); self.side_status.set(text,tone)

    def _async(self,label,fn,done=None):
        if self.busy:return
        try:
            self._settings_from_ui()
            self._worker_bind_password=self.bind_password_var.get() if hasattr(self,"bind_password_var") else ""
            self._worker_user={"login":self.var_login.get().strip(),"email":self.var_email.get().strip(),"password":self.var_password.get()}
        except Exception as e:
            messagebox.showerror(APP_NAME,str(e)); return
        self.busy=True; self._status(label,"warn")
        def worker():
            try:r=fn(); self.after(0,lambda:self._async_done(True,r,done))
            except Exception as e:
                tb=traceback.format_exc(); self.after(0,lambda:self._async_done(False,(e,tb),done))
        threading.Thread(target=worker,daemon=True).start()

    def _async_done(self,ok,payload,done):
        self.busy=False
        if ok:
            self._status("LDAP доступен","good")
            if done: done(payload)
        else:
            e,tb=payload; self._status("Ошибка LDAP","bad"); self._log(f"ОШИБКА: {e}"); self._log(tb); messagebox.showerror(APP_NAME,str(e))

    def test_connection(self):
        def task():
            c=self._connect(); h=self.cfg["ldap_host"]; p=self.cfg["ldap_port"]; c.unbind(); return h,p
        self._async("Проверка…",task,lambda x:(self._log(f"Подключение успешно: {x[0]}:{x[1]}"),messagebox.showinfo(APP_NAME,f"Подключение и Bind успешны.\n{x[0]}:{x[1]}")))

    def generate_password(self):
        alpha=string.ascii_letters+string.digits+"!@#$%_-+=?"
        while True:
            pw="".join(secrets.choice(alpha) for _ in range(18))
            if any(c.islower() for c in pw) and any(c.isupper() for c in pw) and any(c.isdigit() for c in pw) and any(c in "!@#$%_-+=?" for c in pw): break
        self.var_password.set(pw); self.current_password_hash=None

    def toggle_password(self): self.pw.configure(show="" if self.var_show_password.get() else "•")
    def copy_password(self):
        if not self.var_password.get(): self.generate_password()
        self.clipboard_clear(); self.clipboard_append(self.var_password.get()); self.update_idletasks(); self._log("Пароль пользователя скопирован")

    def _next_uid(self,c):
        start=int(self.cfg.get("uid_start",10000)); c.search(self.user_base(),"(uidNumber=*)",SUBTREE,attributes=["uidNumber"]); m=start-1
        for e in c.entries:
            try:m=max(m,int(str(e.uidNumber.value)))
            except:pass
        return m+1

    def _prepare(self,c):
        u=self._worker_user; login=u["login"]; email=u["email"]; password=u["password"]
        if not login: raise ValueError("Введите логин")
        if any(ch in ',=+<>#;"\\ ' for ch in login): raise ValueError("Логин содержит недопустимый символ")
        if not email: raise ValueError("Не задан почтовый домен")
        if not password: raise ValueError("Сгенерируйте или введите пароль")
        filt=f"(|(uid={escape_filter(login)})(mail={escape_filter(email)})(cn={escape_filter(login)}))"
        c.search(self.user_base(),filt,SUBTREE,attributes=["uid","mail","cn"])
        if c.entries: raise ValueError("Пользователь с таким uid, cn или mail уже существует:\n" + "\n".join(str(e.entry_dn) for e in c.entries[:5]))
        dn=self.user_dn(login); c.search(dn,"(objectClass=*)",BASE,attributes=["objectClass"])
        if c.entries: raise ValueError(f"DN уже существует:\n{dn}")
        uid=self._next_uid(c); gid=int(self.cfg.get("fixed_gid",10000)) if self.cfg.get("gid_mode")=="fixed" else uid
        ph=make_ssha(password)
        attrs={"objectClass":["inetOrgPerson","organizationalPerson","person","posixAccount","top"],"cn":login,"gidNumber":str(gid),"homeDirectory":f"{self.cfg.get('home_prefix','/home').rstrip('/')}/{login}","sn":login,"uid":login,"uidNumber":str(uid),"loginShell":self.cfg.get("login_shell","/bin/bash"),"mail":email,"userPassword":ph}
        return {"login":login,"email":email,"dn":dn,"uid":uid,"gid":gid,"attrs":attrs}

    def _group_attr(self,c,dn):
        c.search(dn,"(objectClass=*)",BASE,attributes=["objectClass","memberUid","member","uniqueMember"])
        if not c.entries: raise ValueError(f"Не удалось прочитать группу: {dn}")
        e=c.entries[0]; ocs={str(x).lower() for x in e.objectClass.values}
        if "posixgroup" in ocs:return "memberUid"
        if "groupofnames" in ocs:return "member"
        if "groupofuniquenames" in ocs:return "uniqueMember"
        names={x.lower() for x in e.entry_attributes}
        if "memberuid" in names:return "memberUid"
        if "member" in names:return "member"
        if "uniquemember" in names:return "uniqueMember"
        raise ValueError(f"Неизвестная схема членства группы: {dn}")

    def load_groups(self):
        def task():
            c=self._connect(); c.search(self.groups_base(),"(objectClass=*)",SUBTREE,attributes=["cn","objectClass"]); g=[]
            for e in c.entries:
                try:
                    cn=str(e.cn.value)
                    if cn:g.append((cn,str(e.entry_dn)))
                except:pass
            c.unbind(); return sorted(g,key=lambda x:x[0].lower())
        self._async("Загрузка групп…",task,lambda g:(self._render_groups(g),self._log(f"Загружено групп: {len(g)}")))

    def _render_groups(self,groups):
        for w in self.group_scroll.inner.winfo_children():w.destroy()
        self.group_rows=[]
        for cn,dn in groups:
            row=tk.Frame(self.group_scroll.inner,bg=COLORS["surface2"],highlightthickness=1,highlightbackground=COLORS["border"]); row.pack(fill="x",padx=4,pady=4)
            v=tk.BooleanVar(False); tk.Checkbutton(row,variable=v,bg=COLORS["surface2"],activebackground=COLORS["surface2"],selectcolor=COLORS["input"],bd=0).pack(side="left",padx=(8,3),pady=9)
            txt=tk.Frame(row,bg=COLORS["surface2"]); txt.pack(side="left",fill="x",expand=True,pady=6)
            tk.Label(txt,text=cn,bg=COLORS["surface2"],fg=COLORS["text"],font=("Segoe UI",9,"bold")).pack(anchor="w")
            tk.Label(txt,text=dn,bg=COLORS["surface2"],fg=COLORS["muted"],font=("Segoe UI",7)).pack(anchor="w")
            self.group_rows.append({"cn":cn,"dn":dn,"var":v,"row":row})

    def _filter_groups(self):
        if not hasattr(self,"group_rows"):return
        q=self.var_group_search.get().strip().lower()
        for g in self.group_rows:
            if not q or q in g["cn"].lower() or q in g["dn"].lower(): g["row"].pack(fill="x",padx=4,pady=4)
            else:g["row"].pack_forget()

    def selected_groups(self): return [g["dn"] for g in self.group_rows if g["var"].get()]

    def dry_run(self):
        if not self.var_password.get(): self.generate_password()
        groups=self.selected_groups()
        def task():
            c=self._connect(); d=self._prepare(c); d["groups"]=[(dn,self._group_attr(c,dn)) for dn in groups]; c.unbind(); return d
        def done(d):
            self.var_uid.set(str(d["uid"])); self.var_gid.set(str(d["gid"])); self.inline.configure(text=f"✓ Проверка пройдена • uid={d['uid']} • gid={d['gid']} • групп: {len(d['groups'])}",fg=COLORS["green"])
            self._log(f"Dry Run OK: {d['login']} | uid={d['uid']} | gid={d['gid']}"); messagebox.showinfo(APP_NAME,f"Проверка успешна.\n\nDN: {d['dn']}\nmail: {d['email']}\nuidNumber: {d['uid']}\ngidNumber: {d['gid']}\nГрупп: {len(d['groups'])}")
        self._async("Dry Run…",task,done)

    def _preview(self):
        login=self.var_login.get().strip()
        if not login: raise ValueError("Введите логин")
        if not self.var_password.get(): self.generate_password()
        uid=self.var_uid.get() if self.var_uid.get().isdigit() else "<AUTO>"; gid=self.var_gid.get() if self.var_gid.get().isdigit() else "<AUTO>"
        attrs={"objectClass":["inetOrgPerson","organizationalPerson","person","posixAccount","top"],"cn":login,"gidNumber":gid,"homeDirectory":f"{self.cfg.get('home_prefix','/home').rstrip('/')}/{login}","sn":login,"uid":login,"uidNumber":uid,"loginShell":self.cfg.get("login_shell","/bin/bash"),"mail":self.var_email.get().strip(),"userPassword":make_ssha(self.var_password.get())}
        return to_ldif(self.user_dn(login),attrs)

    def preview_ldif(self):
        try:text=self._preview()
        except Exception as e:messagebox.showerror(APP_NAME,str(e));return
        w=tk.Toplevel(self); w.title("Предпросмотр LDIF"); w.geometry("760x620"); w.configure(bg=COLORS["bg"])
        tk.Label(w,text="Предпросмотр LDIF",bg=COLORS["bg"],fg=COLORS["text"],font=("Segoe UI",16,"bold")).pack(anchor="w",padx=20,pady=(18,10))
        t=tk.Text(w,bg=COLORS["input"],fg="#D7E2F0",insertbackground=COLORS["text"],relief="flat",bd=0,font=("Consolas",10)); t.pack(fill="both",expand=True,padx=20,pady=(0,14)); t.insert("1.0",text); t.configure(state="disabled")

    def save_ldif(self):
        if not self.var_password.get(): self.generate_password()
        def task():
            c=self._connect(); d=self._prepare(c); c.unbind(); return d
        def done(d):
            path=filedialog.asksaveasfilename(defaultextension=".ldif",filetypes=[("LDIF","*.ldif")],initialfile=f"{d['login']}.ldif")
            if path:Path(path).write_text(to_ldif(d["dn"],d["attrs"]),encoding="utf-8");self._log(f"LDIF сохранён: {path}")
        self._async("Подготовка LDIF…",task,done)

    def create_user(self):
        if not self.var_password.get(): self.generate_password()
        groups=self.selected_groups()
        def prep():
            c=self._connect(); d=self._prepare(c); d["groups"]=[(dn,self._group_attr(c,dn)) for dn in groups]; c.unbind(); return d
        def prepared(d):
            self.var_uid.set(str(d["uid"])); self.var_gid.set(str(d["gid"]))
            if messagebox.askyesno(APP_NAME,f"Создать пользователя?\n\nDN: {d['dn']}\nmail: {d['email']}\nuidNumber: {d['uid']}\ngidNumber: {d['gid']}\nГрупп: {len(d['groups'])}"): self._write(d)
        self._async("Проверка перед созданием…",prep,prepared)

    def _write(self,d):
        def task():
            c=self._connect(); login,email,dn=d["login"],d["email"],d["dn"]
            filt=f"(|(uid={escape_filter(login)})(mail={escape_filter(email)})(cn={escape_filter(login)}))"; c.search(self.user_base(),filt,SUBTREE,attributes=["uid"])
            if c.entries: raise ValueError("Пользователь появился после Dry Run; создание отменено")
            if not c.add(dn,attributes=d["attrs"]): raise RuntimeError(f"LDAP ADD: {c.result}")
            errs=[]
            for gdn,attr in d["groups"]:
                val=login if attr=="memberUid" else dn
                if not c.modify(gdn,{attr:[(MODIFY_ADD,[val])]}) and c.result.get("result")!=20: errs.append(f"{gdn}: {c.result}")
            c.unbind(); return errs
        def done(errs):
            self.inline.configure(text="✓ Пользователь создан",fg=COLORS["green"]); self._log(f"СОЗДАН: {d['dn']} | mail={d['email']} | uid={d['uid']} | gid={d['gid']}")
            if errs: messagebox.showwarning(APP_NAME,"Пользователь создан, но есть ошибки групп:\n\n"+"\n".join(errs))
            else: messagebox.showinfo(APP_NAME,f"Пользователь успешно создан.\n\n{d['dn']}\n{d['email']}")
        self._async("Создание…",task,done)

    def _log(self,msg):
        line=f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"; self.log_lines.append(line)
        if hasattr(self,"log_text"):
            self.log_text.configure(state="normal"); self.log_text.insert("end",line+"\n"); self.log_text.see("end"); self.log_text.configure(state="disabled")
    def clear_log(self):
        self.log_lines.clear(); self.log_text.configure(state="normal"); self.log_text.delete("1.0","end"); self.log_text.configure(state="disabled")
    def export_log(self):
        p=filedialog.asksaveasfilename(defaultextension=".log",initialfile="ldap-user-manager.log")
        if p:Path(p).write_text("\n".join(self.log_lines)+"\n",encoding="utf-8")
    def _close(self):
        try:self._settings_from_ui();self._save_config()
        except:pass
        self.destroy()

if __name__=="__main__":
    App().mainloop()
