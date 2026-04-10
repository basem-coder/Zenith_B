#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
نظام جوهرة تعز المحاسبي المتكامل - إصدار MVVM متكامل
مع إضافة شاشة متابعة الاحتياجات الاحترافية (1-11)
تم إعادة الهيكلة باستخدام نمط Model-View-ViewModel مع ربط بيانات تلقائي
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import sqlite3
import hashlib
import os
import shutil
import sys
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime, timedelta
import json
import time
from functools import wraps
from fpdf import FPDF
import re
from typing import List, Dict, Any, Callable, Optional
from dataclasses import dataclass, field
from enum import Enum

# ----------------------------- إعدادات أولية -----------------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
plt.rcParams['font.sans-serif'] = ['Arial']
plt.rcParams['axes.unicode_minus'] = False

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    ARABIC_SUPPORT = True
except ImportError:
    ARABIC_SUPPORT = False

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_documents_path():
    path = os.path.join(os.path.expanduser("~"), "Documents", "JawharaERP")
    os.makedirs(path, exist_ok=True)
    return path

DOCS_PATH = get_documents_path()
DB_PATH = os.path.join(DOCS_PATH, "jawhara_mall_advanced.db")

for folder in ['backups', 'reports', 'invoices', 'receipts', 'whatsapp', 'qrcodes', 'logs', 'attachments']:
    os.makedirs(os.path.join(DOCS_PATH, folder), exist_ok=True)

# ----------------------------- أدوات MVVM المساعدة -----------------------------
class Observable:
    def __init__(self, initial_value=None):
        self._value = initial_value
        self._callbacks = []
    
    @property
    def value(self):
        return self._value
    
    @value.setter
    def value(self, new_value):
        if new_value != self._value:
            self._value = new_value
            self._notify()
    
    def bind(self, callback):
        self._callbacks.append(callback)
        callback(self._value)
    
    def _notify(self):
        for cb in self._callbacks:
            cb(self._value)

class Command:
    def __init__(self, execute: Callable, can_execute: Callable[[], bool] = None):
        self.execute = execute
        self.can_execute = can_execute or (lambda: True)
    
    def __call__(self, *args, **kwargs):
        if self.can_execute():
            return self.execute(*args, **kwargs)

class ViewModelBase:
    def __init__(self, app):
        self.app = app
    
    def on_property_changed(self, prop_name):
        pass

# ----------------------------- النماذج (Models) -----------------------------
@dataclass
class Tenant:
    id: int = 0
    shop: str = ""
    name: str = ""
    phone: str = ""
    whatsapp: str = ""
    rent: float = 0.0
    rent_start_date: str = ""
    contract_end: str = ""
    last_electricity_read: float = 0.0
    last_water_read: float = 0.0
    active: int = 1
    rent_debit: float = 0.0
    rent_credit: float = 0.0
    services_debit: float = 0.0
    services_credit: float = 0.0

@dataclass
class Service:
    id: int = 0
    name: str = ""
    unit_price: float = 0.0
    monthly_fee: float = 0.0
    billing_type: str = "monthly"
    billing_days: str = ""
    is_active: int = 1

@dataclass
class Receipt:
    id: int = 0
    receipt_no: str = ""
    receipt_type: str = ""
    receipt_date: str = ""
    amount: float = 0.0
    payment_method: str = ""
    revenue_type: str = ""
    notes: str = ""
    tenant_id: int = 0
    emp_id: int = 0
    box_id: int = 0
    created_by: str = ""
    status: str = "draft"

@dataclass
class Requirement:
    id: int = 0
    title: str = ""
    description: str = ""
    category: str = ""
    priority: int = 0
    status: str = "planned"
    created_at: str = ""
    updated_at: str = ""

# ----------------------------- مستودع البيانات (Repository) -----------------------------
class Repository:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()
    
    def _execute(self, query, params=(), fetchone=False, fetchall=False, commit=False):
        try:
            with sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute(query, params)
                if commit:
                    conn.commit()
                if fetchone:
                    row = c.fetchone()
                    return dict(row) if row else None
                if fetchall:
                    rows = c.fetchall()
                    return [dict(row) for row in rows]
                return c.lastrowid
        except sqlite3.Error as e:
            print(f"DB Error: {e}")
            raise
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            # جداول النظام الأساسية
            c.execute('''CREATE TABLE IF NOT EXISTS tenants (
                id INTEGER PRIMARY KEY AUTOINCREMENT, shop TEXT UNIQUE, name TEXT, phone TEXT,
                rent REAL DEFAULT 0, rent_start_date DATE, last_electricity_read REAL DEFAULT 0,
                last_water_read REAL DEFAULT 0, whatsapp TEXT, contract_end DATE,
                active INTEGER DEFAULT 1, rent_debit REAL DEFAULT 0, rent_credit REAL DEFAULT 0,
                services_debit REAL DEFAULT 0, services_credit REAL DEFAULT 0
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT,
                role TEXT, full_name TEXT, permissions TEXT, last_login TIMESTAMP, active INTEGER DEFAULT 1
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS cashboxes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, balance REAL DEFAULT 0,
                min_balance REAL DEFAULT 0, box_type TEXT DEFAULT 'عام', created_date DATE, active INTEGER DEFAULT 1
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, unit_price REAL DEFAULT 0,
                monthly_fee REAL DEFAULT 0, billing_type TEXT DEFAULT 'monthly', billing_days TEXT,
                is_active INTEGER DEFAULT 1
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT, emp_code TEXT UNIQUE, name TEXT, phone TEXT,
                position TEXT, salary REAL DEFAULT 0, department_id INTEGER, allowance REAL DEFAULT 0,
                deduction REAL DEFAULT 0, advance REAL DEFAULT 0, active INTEGER DEFAULT 1
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, active INTEGER DEFAULT 1
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT UNIQUE, receipt_type TEXT,
                receipt_date DATE, amount REAL, payment_method TEXT, ref_type TEXT, ref_id INTEGER,
                tenant_id INTEGER, emp_id INTEGER, box_id INTEGER, notes TEXT, created_by TEXT,
                branch TEXT, cost_center TEXT, reference_no TEXT, attachment TEXT, currency TEXT,
                exchange_rate REAL, account_id INTEGER, status TEXT, revenue_type TEXT, print_count INTEGER DEFAULT 0
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS electricity_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER, reading_date DATE,
                previous_read REAL DEFAULT 0, current_read REAL DEFAULT 0, consumption REAL DEFAULT 0,
                amount REAL DEFAULT 0, due_date DATE, paid INTEGER DEFAULT 0, invoice_id INTEGER,
                UNIQUE(tenant_id, reading_date)
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS water_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER, reading_date DATE,
                previous_read REAL DEFAULT 0, current_read REAL DEFAULT 0, consumption REAL DEFAULT 0,
                amount REAL DEFAULT 0, due_date DATE, paid INTEGER DEFAULT 0, invoice_id INTEGER,
                UNIQUE(tenant_id, reading_date)
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS tenant_services (
                tenant_id INTEGER, service_id INTEGER, is_active INTEGER DEFAULT 1,
                PRIMARY KEY (tenant_id, service_id)
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS tenant_service_prices (
                tenant_id INTEGER, service_id INTEGER, custom_price REAL,
                PRIMARY KEY (tenant_id, service_id)
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS monthly_rent_due (
                id INTEGER PRIMARY KEY AUTOINCREMENT, due_date DATE, processed INTEGER DEFAULT 0,
                processed_date DATE
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS salaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT, emp_id INTEGER, department_id INTEGER,
                month TEXT, basic REAL DEFAULT 0, allowances REAL DEFAULT 0, deductions REAL DEFAULT 0,
                advances REAL DEFAULT 0, absences REAL DEFAULT 0, net REAL DEFAULT 0, due_date DATE,
                paid INTEGER DEFAULT 0, payment_date DATE, receipt_id INTEGER
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, name TEXT, acc_type TEXT,
                parent_id INTEGER, is_active INTEGER DEFAULT 1
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS journal_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT, entry_no TEXT UNIQUE, entry_date DATE,
                description TEXT, status TEXT DEFAULT 'draft', created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, posted_at TIMESTAMP
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS journal_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT, entry_id INTEGER, account_id INTEGER,
                debit REAL DEFAULT 0, credit REAL DEFAULT 0, memo TEXT
            )''')
            # جدول الاحتياجات الاحترافية
            c.execute('''CREATE TABLE IF NOT EXISTS requirements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT,
                priority INTEGER DEFAULT 0,
                status TEXT DEFAULT 'planned',
                created_at DATE,
                updated_at DATE
            )''')
            
            # المستخدم الافتراضي والبيانات الأولية
            self._ensure_default_user(c)
            # إدراج الاحتياجات الـ 11 إذا كان الجدول فارغاً
            self._insert_requirements(c)
            conn.commit()
    
    def _ensure_default_user(self, c):
        c.execute("SELECT COUNT(*) FROM users")
        if c.fetchone()[0] == 0:
            admin_pw = hashlib.sha256("basem2026".encode()).hexdigest()
            c.execute('''INSERT INTO users (username, password, role, full_name, permissions, last_login, active)
                         VALUES (?, ?, ?, ?, ?, ?, ?)''',
                      ("admin", admin_pw, "Admin", "مدير النظام", json.dumps({'all': True}), datetime.now(), 1))
            # بيانات أولية للصناديق والخدمات
            c.execute("INSERT OR IGNORE INTO cashboxes (name, box_type, balance, created_date) VALUES (?, ?, ?, ?)",
                      ("الصندوق الرئيسي", "رئيسي", 0, datetime.now().date()))
            c.execute("INSERT OR IGNORE INTO cashboxes (name, box_type, created_date) VALUES (?, ?, ?)",
                      ("صندوق الكهرباء", "كهرباء", datetime.now().date()))
            c.execute("INSERT OR IGNORE INTO cashboxes (name, box_type, created_date) VALUES (?, ?, ?)",
                      ("صندوق الإيجارات", "إيجارات", datetime.now().date()))
            c.execute("INSERT OR IGNORE INTO cashboxes (name, box_type, created_date) VALUES (?, ?, ?)",
                      ("صندوق الماء", "ماء", datetime.now().date()))
            c.execute("INSERT OR IGNORE INTO services (name, unit_price, monthly_fee, billing_days) VALUES (?, ?, ?, ?)",
                      ("كهرباء", 50, 100, "15,28"))
            c.execute("INSERT OR IGNORE INTO services (name, unit_price, monthly_fee, billing_days) VALUES (?, ?, ?, ?)",
                      ("ماء", 30, 50, "25"))
            default = {'company_name': 'جوهرة تعز مول', 'min_cash_alert': '5000',
                       'alert_interval': '60', 'days_before_contract': '30',
                       'receipt_prefix': 'RCT', 'rent_invoice_prefix': 'RENT'}
            for k, v in default.items():
                c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
    
    def _insert_requirements(self, c):
        count = c.execute("SELECT COUNT(*) FROM requirements").fetchone()[0]
        if count == 0:
            requirements_data = [
                (1, "🔐 الأمان وإدارة الصلاحيات", "تشفير أقوى، صلاحيات دقيقة (RBAC)، تسجيل الدخول بعاملين، سجل التدقيق.", "أمان", 1, "planned"),
                (2, "📚 المحاسبة والقيد المزدوج", "قيد يومي تلقائي، دليل حسابات متكامل، إقفال الفترات المالية، ميزان مراجعة حقيقي.", "محاسبة", 1, "planned"),
                (3, "🧾 الفواتير والإيصالات", "ترقيم تسلسلي آمن، طباعة قوالب متعددة، دعم الشيكات.", "مالية", 2, "planned"),
                (4, "📊 التقارير والتحليلات الاحترافية", "لوحة تحكم KPI، تقارير مخصصة، جدولة التقارير، تحليل التعثر (Aging).", "تقارير", 2, "planned"),
                (5, "💰 التعامل مع العملات والأسعار", "دعم عملات متعددة، فروق العملات، تحديث أسعار الصرف.", "مالية", 3, "planned"),
                (6, "🔔 نظام التنبيهات والإشعارات", "تنبيهات داخلية قابلة للتخصيص، إشعارات عبر البريد الإلكتروني وواتساب.", "تنبيهات", 2, "planned"),
                (7, "🧰 أدوات مساعدة متقدمة", "نسخ احتياطي تلقائي، استعادة البيانات، إدارة المرفقات، سجل عمليات.", "أدوات", 1, "planned"),
                (8, "🧪 الاختبارات والجودة", "اختبارات وحدوية وتكامل، CI/CD.", "جودة", 3, "planned"),
                (9, "🖥️ واجهة المستخدم وتجربة المستخدم", "دعم الوضع الليلي/النهاري الديناميكي، شاشات سريعة الاستجابة، اختصارات لوحة المفاتيح، بحث متقدم.", "UI/UX", 3, "planned"),
                (10, "🌐 قابلية التوسع والنشر", "واجهة REST API، تحديث تلقائي، دعم قواعد بيانات متعددة.", "بنية تحتية", 2, "planned"),
                (11, "📜 الامتثال للمعايير المحاسبية والقانونية", "التوافق مع ضريبة القيمة المضافة، IFRS for SMEs، إقفال سنوي.", "قانوني", 2, "planned"),
            ]
            for req in requirements_data:
                c.execute('''INSERT INTO requirements (id, title, description, category, priority, status, created_at)
                             VALUES (?, ?, ?, ?, ?, ?, ?)''',
                          (req[0], req[1], req[2], req[3], req[4], req[5], datetime.now().date()))
    
    # ------------------- دوال الوصول للبيانات -------------------
    def get_all_tenants(self, active_only=True):
        where = "WHERE active=1" if active_only else ""
        return self._execute(f"SELECT * FROM tenants {where} ORDER BY shop", fetchall=True)
    
    def get_tenant_by_id(self, tenant_id):
        return self._execute("SELECT * FROM tenants WHERE id=?", (tenant_id,), fetchone=True)
    
    def add_tenant(self, tenant: Tenant):
        return self._execute("""
            INSERT INTO tenants (shop, name, phone, whatsapp, rent, rent_start_date, contract_end)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (tenant.shop, tenant.name, tenant.phone, tenant.whatsapp, tenant.rent,
              tenant.rent_start_date, tenant.contract_end), commit=True)
    
    def update_tenant(self, tenant: Tenant):
        self._execute("""
            UPDATE tenants SET name=?, phone=?, whatsapp=?, rent=?, rent_start_date=?, contract_end=?
            WHERE id=?
        """, (tenant.name, tenant.phone, tenant.whatsapp, tenant.rent,
              tenant.rent_start_date, tenant.contract_end, tenant.id), commit=True)
    
    def delete_tenant(self, tenant_id):
        self._execute("UPDATE tenants SET active=0 WHERE id=?", (tenant_id,), commit=True)
    
    def get_all_services(self):
        return self._execute("SELECT * FROM services ORDER BY name", fetchall=True)
    
    def add_service(self, service: Service):
        return self._execute("""
            INSERT INTO services (name, unit_price, monthly_fee, billing_days)
            VALUES (?, ?, ?, ?)
        """, (service.name, service.unit_price, service.monthly_fee, service.billing_days), commit=True)
    
    def update_service(self, service: Service):
        self._execute("""
            UPDATE services SET unit_price=?, monthly_fee=?, billing_days=?, is_active=?
            WHERE id=?
        """, (service.unit_price, service.monthly_fee, service.billing_days, service.is_active, service.id), commit=True)
    
    def delete_service(self, service_id):
        self._execute("DELETE FROM services WHERE id=?", (service_id,), commit=True)
    
    def get_readings(self, table, tenant_id=None):
        if tenant_id:
            return self._execute(f"SELECT * FROM {table} WHERE tenant_id=? ORDER BY reading_date DESC", (tenant_id,), fetchall=True)
        return self._execute(f"SELECT * FROM {table} ORDER BY reading_date DESC", fetchall=True)
    
    def add_reading(self, table, data):
        return self._execute(f"""
            INSERT INTO {table} (tenant_id, reading_date, previous_read, current_read, consumption, amount, due_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, data, commit=True)
    
    def get_all_cashboxes(self):
        return self._execute("SELECT * FROM cashboxes WHERE active=1 ORDER BY name", fetchall=True)
    
    def add_cashbox(self, name, box_type, balance):
        return self._execute("INSERT INTO cashboxes (name, box_type, balance, created_date) VALUES (?, ?, ?, ?)",
                             (name, box_type, balance, datetime.now().date()), commit=True)
    
    def update_cashbox_balance(self, box_id, amount_delta):
        self._execute("UPDATE cashboxes SET balance = balance + ? WHERE id=?", (amount_delta, box_id), commit=True)
    
    def add_receipt(self, receipt: Receipt):
        receipt_id = self._execute("""
            INSERT INTO receipts (receipt_type, receipt_date, amount, payment_method, revenue_type, notes, created_by, box_id, tenant_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (receipt.receipt_type, receipt.receipt_date, receipt.amount, receipt.payment_method,
              receipt.revenue_type, receipt.notes, receipt.created_by, receipt.box_id, receipt.tenant_id, receipt.status), commit=True)
        prefix = "RCP" if receipt.receipt_type == "قبض" else "PAY"
        receipt_no = f"{prefix}-{receipt_id:06d}"
        self._execute("UPDATE receipts SET receipt_no=? WHERE id=?", (receipt_no, receipt_id), commit=True)
        return receipt_id, receipt_no
    
    def get_receipts(self, receipt_type=None):
        if receipt_type:
            return self._execute("SELECT * FROM receipts WHERE receipt_type=? ORDER BY receipt_date DESC", (receipt_type,), fetchall=True)
        return self._execute("SELECT * FROM receipts ORDER BY receipt_date DESC", fetchall=True)
    
    def get_receipt_by_no(self, receipt_no):
        return self._execute("SELECT * FROM receipts WHERE receipt_no=?", (receipt_no,), fetchone=True)
    
    def get_dashboard_stats(self):
        total_tenants = self._execute("SELECT COUNT(*) FROM tenants WHERE active=1", fetchone=True)['COUNT(*)'] or 0
        rent_revenue = self._execute("SELECT COALESCE(SUM(amount),0) FROM receipts WHERE receipt_type='قبض' AND revenue_type='إيجار'", fetchone=True)['COALESCE(SUM(amount),0)'] or 0
        elec_revenue = self._execute("SELECT COALESCE(SUM(amount),0) FROM receipts WHERE receipt_type='قبض' AND revenue_type='كهرباء'", fetchone=True)['COALESCE(SUM(amount),0)'] or 0
        water_revenue = self._execute("SELECT COALESCE(SUM(amount),0) FROM receipts WHERE receipt_type='قبض' AND revenue_type='ماء'", fetchone=True)['COALESCE(SUM(amount),0)'] or 0
        expenses = self._execute("SELECT COALESCE(SUM(amount),0) FROM receipts WHERE receipt_type='صرف'", fetchone=True)['COALESCE(SUM(amount),0)'] or 0
        total_cash = self._execute("SELECT COALESCE(SUM(balance),0) FROM cashboxes", fetchone=True)['COALESCE(SUM(balance),0)'] or 0
        rent_debt = self._execute("SELECT COALESCE(SUM(rent_debit - rent_credit),0) FROM tenants", fetchone=True)['COALESCE(SUM(rent_debit - rent_credit),0)'] or 0
        return {
            'total_tenants': total_tenants,
            'rent_revenue': rent_revenue,
            'electricity_revenue': elec_revenue,
            'water_revenue': water_revenue,
            'total_expenses': expenses,
            'total_cash': total_cash,
            'total_rent_debt': rent_debt
        }
    
    def get_chart_data(self):
        return self._execute('''
            SELECT strftime('%Y-%m', receipt_date) as month,
                   COALESCE(SUM(CASE WHEN revenue_type='إيجار' THEN amount ELSE 0 END),0) as rent,
                   COALESCE(SUM(CASE WHEN revenue_type='كهرباء' THEN amount ELSE 0 END),0) as elec,
                   COALESCE(SUM(CASE WHEN revenue_type='ماء' THEN amount ELSE 0 END),0) as water
            FROM receipts WHERE receipt_type='قبض'
            GROUP BY month ORDER BY month DESC LIMIT 6
        ''', fetchall=True)
    
    def authenticate_user(self, username, password):
        hashed = hashlib.sha256(password.encode()).hexdigest()
        return self._execute("SELECT username, full_name, role, permissions FROM users WHERE username=? AND password=? AND active=1",
                             (username, hashed), fetchone=True)
    
    def get_setting(self, key, default=None):
        res = self._execute("SELECT value FROM settings WHERE key=?", (key,), fetchone=True)
        return res['value'] if res else default
    
    def set_setting(self, key, value):
        self._execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value), commit=True)
    
    # دوال الاحتياجات
    def get_all_requirements(self):
        return self._execute("SELECT * FROM requirements ORDER BY priority, id", fetchall=True)
    
    def update_requirement_status(self, req_id, new_status):
        self._execute("UPDATE requirements SET status=?, updated_at=? WHERE id=?", (new_status, datetime.now().date(), req_id), commit=True)

# ----------------------------- دوال مساعدة (PDF، تفقيط) -----------------------------
def number_to_arabic_words(num):
    if num == 0:
        return "صفر"
    units = ["", "واحد", "اثنان", "ثلاثة", "أربعة", "خمسة", "ستة", "سبعة", "ثمانية", "تسعة"]
    tens = ["", "عشرة", "عشرون", "ثلاثون", "أربعون", "خمسون", "ستون", "سبعون", "ثمانون", "تسعون"]
    hundreds = ["", "مائة", "مئتان", "ثلاثمائة", "أربعمائة", "خمسمائة", "ستمائة", "سبعمائة", "ثمانمائة", "تسعمائة"]
    def convert_three_digits(n):
        result = ""
        h = n // 100
        if h > 0:
            result += hundreds[h] + " "
            n %= 100
        if n >= 10 and n <= 19:
            if n == 10:
                result += "عشرة "
            elif n == 11:
                result += "أحد عشر "
            elif n == 12:
                result += "اثنا عشر "
            else:
                result += units[n % 10] + " " + tens[1] + " "
            return result
        else:
            t = n // 10
            u = n % 10
            if t > 0:
                result += tens[t] + " "
            if u > 0:
                result += units[u] + " "
            return result
    num_parts = []
    millions = num // 1000000
    if millions > 0:
        num_parts.append(convert_three_digits(millions) + "مليون ")
        num %= 1000000
    thousands = num // 1000
    if thousands > 0:
        if thousands == 1:
            num_parts.append("ألف ")
        else:
            num_parts.append(convert_three_digits(thousands) + "ألف ")
        num %= 1000
    if num > 0:
        num_parts.append(convert_three_digits(num))
    return "".join(num_parts).strip()

class CustomPDF(FPDF):
    def __init__(self, company_name="جوهرة تعز مول", logo_path=None):
        super().__init__()
        self.company_name = company_name
        self.logo_path = logo_path
        self.set_auto_page_break(auto=True, margin=25)
        self.arabic_font = None
        self._load_arabic_font()
    
    def _load_arabic_font(self):
        font_files = ["arial.ttf", "Arial.ttf", "arialuni.ttf", "DejaVuSans.ttf"]
        search_paths = ["C:/Windows/Fonts/", "/usr/share/fonts/truetype/", os.path.join(os.environ.get("HOME", ""), ".fonts/")]
        for path in search_paths:
            for font_file in font_files:
                full_path = os.path.join(path, font_file)
                if os.path.exists(full_path):
                    try:
                        self.add_font('ArabicFont', '', full_path, uni=True)
                        self.arabic_font = 'ArabicFont'
                        return
                    except:
                        continue
    
    def _prepare_arabic_text(self, text):
        if not self.arabic_font:
            return text
        if not any('\u0600' <= c <= '\u06FF' for c in text):
            return text
        if ARABIC_SUPPORT:
            try:
                reshaped = arabic_reshaper.reshape(text)
                return get_display(reshaped)
            except:
                return text[::-1]
        else:
            return text[::-1]
    
    def cell(self, w, h=0, txt='', border=0, ln=0, align='', fill=False, link=''):
        txt = self._prepare_arabic_text(txt)
        if self.arabic_font:
            self.set_font(self.arabic_font, '', 10)
        super().cell(w, h, txt, border, ln, align, fill, link)
    
    def header(self):
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                self.image(self.logo_path, 10, 8, 25)
            except:
                pass
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, self.company_name, 0, 1, 'C')
        self.ln(5)
        self.line(10, 30, 200, 30)
        self.ln(5)
    
    def footer(self):
        self.set_y(-25)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, 'المدير المالي: باسم فتح حقيس', 0, 0, 'L')
        self.cell(0, 10, 'المستلم: _________________', 0, 0, 'R')

# ----------------------------- ViewModels -----------------------------
class TenantsViewModel(ViewModelBase):
    def __init__(self, app):
        super().__init__(app)
        self.repo = app.repository
        self.tenants = Observable([])
        self.selected_tenant = Observable(None)
        self.shop = Observable("")
        self.name = Observable("")
        self.phone = Observable("")
        self.whatsapp = Observable("")
        self.rent = Observable(0.0)
        self.rent_start_date = Observable("")
        self.contract_end = Observable("")
        self.load_tenants_command = Command(self.load_tenants)
        self.add_tenant_command = Command(self.add_tenant, self.can_add_tenant)
        self.update_tenant_command = Command(self.update_tenant, lambda: self.selected_tenant.value is not None)
        self.delete_tenant_command = Command(self.delete_tenant, lambda: self.selected_tenant.value is not None)
        self.export_excel_command = Command(self.export_excel)
        self.import_excel_command = Command(self.import_excel)
        self.export_template_command = Command(self.export_template)
        self.load_tenants()
    
    def load_tenants(self):
        self.tenants.value = self.repo.get_all_tenants()
    
    def can_add_tenant(self):
        return bool(self.shop.value and self.name.value)
    
    def add_tenant(self):
        tenant = Tenant(shop=self.shop.value, name=self.name.value, phone=self.phone.value,
                       whatsapp=self.whatsapp.value, rent=float(self.rent.value or 0),
                       rent_start_date=self.rent_start_date.value, contract_end=self.contract_end.value)
        self.repo.add_tenant(tenant)
        self.load_tenants()
        self.shop.value = ""; self.name.value = ""; self.phone.value = ""; self.whatsapp.value = ""
        self.rent.value = 0.0; self.rent_start_date.value = ""; self.contract_end.value = ""
        self.app.show_message("نجاح", "تم إضافة المستأجر", "info")
    
    def update_tenant(self):
        if not self.selected_tenant.value: return
        tenant = Tenant(**self.selected_tenant.value)
        tenant.name = self.name.value; tenant.phone = self.phone.value; tenant.whatsapp = self.whatsapp.value
        tenant.rent = float(self.rent.value or 0); tenant.rent_start_date = self.rent_start_date.value
        tenant.contract_end = self.contract_end.value
        self.repo.update_tenant(tenant)
        self.load_tenants()
        self.app.show_message("نجاح", "تم التحديث", "info")
    
    def delete_tenant(self):
        if self.selected_tenant.value and self.app.show_message("تأكيد", "حذف المستأجر؟", "question"):
            self.repo.delete_tenant(self.selected_tenant.value['id'])
            self.load_tenants()
            self.selected_tenant.value = None
    
    def set_selected_tenant(self, tenant_dict):
        self.selected_tenant.value = tenant_dict
        if tenant_dict:
            self.name.value = tenant_dict['name']; self.phone.value = tenant_dict['phone'] or ""
            self.whatsapp.value = tenant_dict['whatsapp'] or ""; self.rent.value = tenant_dict['rent']
            self.rent_start_date.value = tenant_dict['rent_start_date'] or ""
            self.contract_end.value = tenant_dict['contract_end'] or ""
    
    def export_excel(self):
        try:
            data = self.repo.get_all_tenants()
            df = pd.DataFrame(data)[['shop','name','phone','whatsapp','rent','rent_start_date','contract_end']]
            df.columns = ['المحل','الاسم','الهاتف','واتساب','الإيجار','تاريخ البدء','تاريخ الانتهاء']
            fname = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile="المستأجرين.xlsx")
            if fname: df.to_excel(fname, index=False); self.app.show_message("نجاح", "تم التصدير", "info")
        except Exception as e: self.app.show_message("خطأ", str(e), "error")
    
    def import_excel(self):
        fname = filedialog.askopenfilename(filetypes=[("Excel files","*.xlsx")])
        if not fname: return
        try:
            df = pd.read_excel(fname)
            for _, row in df.iterrows():
                shop = str(row.get('المحل','')); name = str(row.get('الاسم',''))
                if shop and name:
                    self.repo.add_tenant(Tenant(shop=shop, name=name, phone=str(row.get('الهاتف','')),
                                                whatsapp=str(row.get('واتساب','')), rent=float(row.get('الإيجار',0)),
                                                rent_start_date=str(row.get('تاريخ البدء','')), contract_end=str(row.get('تاريخ الانتهاء',''))))
            self.load_tenants(); self.app.show_message("نجاح", "تم الاستيراد", "info")
        except Exception as e: self.app.show_message("خطأ", f"فشل الاستيراد: {e}", "error")
    
    def export_template(self):
        try:
            df = pd.DataFrame({"المحل":["مثال1"],"الاسم":["شركة الأمل"],"الهاتف":["777777777"],"واتساب":["777777777"],"الإيجار":[5000],"تاريخ البدء":["2026-01-01"],"تاريخ الانتهاء":["2027-01-01"]})
            fname = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile="نموذج_المستأجرين.xlsx")
            if fname: df.to_excel(fname, index=False); self.app.show_message("نجاح", "تم تصدير النموذج", "info")
        except Exception as e: self.app.show_message("خطأ", str(e), "error")

class ServicesViewModel(ViewModelBase):
    def __init__(self, app):
        super().__init__(app)
        self.repo = app.repository
        self.services = Observable([])
        self.selected_service = Observable(None)
        self.name = Observable("")
        self.unit_price = Observable(0.0)
        self.monthly_fee = Observable(0.0)
        self.billing_days = Observable("")
        self.load_services_command = Command(self.load_services)
        self.add_service_command = Command(self.add_service, lambda: bool(self.name.value))
        self.update_service_command = Command(self.update_service, lambda: self.selected_service.value is not None)
        self.delete_service_command = Command(self.delete_service, lambda: self.selected_service.value is not None)
        self.toggle_service_command = Command(self.toggle_service, lambda: self.selected_service.value is not None)
        self.load_services()
    
    def load_services(self):
        self.services.value = self.repo.get_all_services()
    
    def add_service(self):
        service = Service(name=self.name.value, unit_price=float(self.unit_price.value or 0),
                          monthly_fee=float(self.monthly_fee.value or 0), billing_days=self.billing_days.value)
        self.repo.add_service(service)
        self.load_services()
        self.name.value = ""; self.unit_price.value = 0.0; self.monthly_fee.value = 0.0; self.billing_days.value = ""
        self.app.show_message("نجاح", "تم إضافة الخدمة", "info")
    
    def update_service(self):
        if not self.selected_service.value: return
        service = Service(**self.selected_service.value)
        service.unit_price = float(self.unit_price.value or 0); service.monthly_fee = float(self.monthly_fee.value or 0)
        service.billing_days = self.billing_days.value
        self.repo.update_service(service)
        self.load_services()
        self.app.show_message("نجاح", "تم التحديث", "info")
    
    def delete_service(self):
        if self.selected_service.value and self.app.show_message("تأكيد", "حذف الخدمة؟", "question"):
            self.repo.delete_service(self.selected_service.value['id'])
            self.load_services()
            self.selected_service.value = None
    
    def toggle_service(self):
        if self.selected_service.value:
            service = Service(**self.selected_service.value)
            service.is_active = 0 if service.is_active else 1
            self.repo.update_service(service)
            self.load_services()
    
    def set_selected_service(self, service_dict):
        self.selected_service.value = service_dict
        if service_dict:
            self.unit_price.value = service_dict['unit_price']
            self.monthly_fee.value = service_dict['monthly_fee']
            self.billing_days.value = service_dict['billing_days'] or ""

class UnifiedReadingsViewModel(ViewModelBase):
    def __init__(self, app):
        super().__init__(app)
        self.repo = app.repository
        self.service_type = Observable("كهرباء")
        self.tenants = Observable([])
        self.selected_tenant = Observable(None)
        self.readings = Observable([])
        self.previous_read = Observable(0.0)
        self.current_read = Observable(0.0)
        self.reading_date = Observable(datetime.now().strftime("%Y-%m-%d"))
        self.load_tenants_command = Command(self.load_tenants)
        self.load_readings_command = Command(self.load_readings, lambda: self.selected_tenant.value is not None)
        self.add_reading_command = Command(self.add_reading, self.can_add_reading)
        self.export_excel_command = Command(self.export_excel, lambda: self.selected_tenant.value is not None)
        self.service_type.bind(lambda _: self.load_tenants())
        self.load_tenants()
    
    def load_tenants(self):
        service = self.service_type.value
        data = self.repo._execute("""
            SELECT t.id, t.shop, t.name FROM tenants t
            JOIN tenant_services ts ON t.id = ts.tenant_id
            JOIN services s ON ts.service_id = s.id
            WHERE s.name = ? AND ts.is_active=1 AND t.active=1
        """, (service,), fetchall=True)
        self.tenants.value = data
    
    def load_readings(self):
        if not self.selected_tenant.value: return
        tenant_id = self.selected_tenant.value['id']
        table = "electricity_readings" if self.service_type.value == "كهرباء" else "water_readings"
        data = self.repo.get_readings(table, tenant_id)
        self.readings.value = data
        self.previous_read.value = data[0]['current_read'] if data else 0.0
    
    def can_add_reading(self):
        return self.selected_tenant.value is not None and self.current_read.value > self.previous_read.value
    
    def add_reading(self):
        tenant_id = self.selected_tenant.value['id']
        service_name = self.service_type.value
        service = self.repo._execute("SELECT id, unit_price, monthly_fee FROM services WHERE name=?", (service_name,), fetchone=True)
        if not service: return
        unit_price = service['unit_price']; monthly_fee = service['monthly_fee']
        custom = self.repo._execute("SELECT custom_price FROM tenant_service_prices WHERE tenant_id=? AND service_id=?", (tenant_id, service['id']), fetchone=True)
        if custom: unit_price = custom['custom_price']
        consumption = self.current_read.value - self.previous_read.value
        amount = consumption * unit_price + monthly_fee
        due_date = (datetime.strptime(self.reading_date.value, "%Y-%m-%d") + timedelta(days=30)).strftime("%Y-%m-%d")
        table = "electricity_readings" if service_name == "كهرباء" else "water_readings"
        self.repo.add_reading(table, (tenant_id, self.reading_date.value, self.previous_read.value,
                                      self.current_read.value, consumption, amount, due_date))
        self.repo._execute("UPDATE tenants SET services_debit = services_debit + ? WHERE id=?", (amount, tenant_id), commit=True)
        box_type = "كهرباء" if service_name == "كهرباء" else "ماء"
        box = self.repo._execute("SELECT id FROM cashboxes WHERE box_type=?", (box_type,), fetchone=True)
        if box: self.repo.update_cashbox_balance(box['id'], amount)
        self.load_readings()
        self.current_read.value = 0.0
        self.app.show_message("نجاح", f"تم إضافة قراءة {service_name}", "info")
    
    def export_excel(self):
        if not self.selected_tenant.value: return
        tenant_id = self.selected_tenant.value['id']
        service_name = self.service_type.value
        table = "electricity_readings" if service_name == "كهرباء" else "water_readings"
        data = self.repo.get_readings(table, tenant_id)
        df = pd.DataFrame(data)
        fname = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=f"قراءات_{service_name}_{self.selected_tenant.value['shop']}.xlsx")
        if fname: df.to_excel(fname, index=False); self.app.show_message("نجاح", "تم التصدير", "info")

class CashboxesViewModel(ViewModelBase):
    def __init__(self, app):
        super().__init__(app)
        self.repo = app.repository
        self.cashboxes = Observable([])
        self.name = Observable("")
        self.box_type = Observable("عام")
        self.balance = Observable(0.0)
        self.load_command = Command(self.load_cashboxes)
        self.add_command = Command(self.add_cashbox, lambda: bool(self.name.value))
        self.load_cashboxes()
    
    def load_cashboxes(self):
        self.cashboxes.value = self.repo.get_all_cashboxes()
    
    def add_cashbox(self):
        self.repo.add_cashbox(self.name.value, self.box_type.value, float(self.balance.value or 0))
        self.load_cashboxes()
        self.name.value = ""; self.balance.value = 0.0
        self.app.show_message("نجاح", "تم إضافة الصندوق", "info")

class ReceiptsViewModel(ViewModelBase):
    def __init__(self, app):
        super().__init__(app)
        self.repo = app.repository
        self.receipts = Observable([])
        self.payments = Observable([])
        self.receipt_date = Observable(datetime.now().strftime("%Y-%m-%d"))
        self.payment_date = Observable(datetime.now().strftime("%Y-%m-%d"))
        self.amount = Observable(0.0)
        self.payment_method = Observable("نقدي")
        self.revenue_type = Observable("إيجار")
        self.notes = Observable("")
        self.selected_tenant_id = Observable(None)
        self.selected_box_id = Observable(None)
        self.tenants_list = Observable([])
        self.boxes_list = Observable([])
        self.amount_words = Observable("")
        self.load_receipts_command = Command(self.load_receipts)
        self.load_payments_command = Command(self.load_payments)
        self.save_receipt_command = Command(self.save_receipt, lambda: self.amount.value > 0)
        self.save_payment_command = Command(self.save_payment, lambda: self.amount.value > 0 and self.selected_box_id.value)
        self.print_receipt_command = Command(self.print_receipt, lambda: self.selected_receipt_no is not None)
        self.print_payment_command = Command(self.print_payment, lambda: self.selected_payment_no is not None)
        self.update_amount_words()
        self.load_tenants(); self.load_boxes()
        self.load_receipts(); self.load_payments()
        self.selected_receipt_no = None; self.selected_payment_no = None
    
    def update_amount_words(self):
        try:
            amt = float(self.amount.value or 0)
            words = number_to_arabic_words(int(amt)) + " ريال"
            if amt - int(amt) > 0: words += f" و {int((amt - int(amt)) * 100)} هللة"
            self.amount_words.value = words
        except: self.amount_words.value = ""
    
    def load_tenants(self):
        tenants = self.repo.get_all_tenants()
        self.tenants_list.value = [(t['id'], f"{t['shop']} - {t['name']}") for t in tenants]
    
    def load_boxes(self):
        boxes = self.repo.get_all_cashboxes()
        self.boxes_list.value = [(b['id'], b['name']) for b in boxes]
    
    def load_receipts(self):
        self.receipts.value = self.repo.get_receipts('قبض')
    
    def load_payments(self):
        self.payments.value = self.repo.get_receipts('صرف')
    
    def save_receipt(self):
        box_map = {"إيجار":"صندوق الإيجارات","كهرباء":"صندوق الكهرباء","ماء":"صندوق الماء","إيراد آخر":"الصندوق الرئيسي"}
        box_name = box_map.get(self.revenue_type.value, "الصندوق الرئيسي")
        box = self.repo._execute("SELECT id FROM cashboxes WHERE name=?", (box_name,), fetchone=True)
        if not box: self.app.show_message("خطأ", f"الصندوق {box_name} غير موجود", "error"); return
        receipt = Receipt(receipt_type="قبض", receipt_date=self.receipt_date.value, amount=float(self.amount.value),
                          payment_method=self.payment_method.value, revenue_type=self.revenue_type.value,
                          notes=self.notes.value, created_by=self.app.current_user, box_id=box['id'],
                          tenant_id=self.selected_tenant_id.value, status="posted")
        rid, rno = self.repo.add_receipt(receipt)
        self.repo.update_cashbox_balance(box['id'], receipt.amount)
        if receipt.tenant_id:
            if receipt.revenue_type == "إيجار":
                self.repo._execute("UPDATE tenants SET rent_credit = rent_credit + ? WHERE id=?", (receipt.amount, receipt.tenant_id), commit=True)
            else:
                self.repo._execute("UPDATE tenants SET services_credit = services_credit + ? WHERE id=?", (receipt.amount, receipt.tenant_id), commit=True)
        self.load_receipts(); self.amount.value = 0.0; self.notes.value = ""
        self.app.show_message("نجاح", f"تم حفظ سند القبض برقم {rno}", "info")
    
    def save_payment(self):
        box_id = self.selected_box_id.value
        box = self.repo._execute("SELECT balance FROM cashboxes WHERE id=?", (box_id,), fetchone=True)
        if box and box['balance'] < self.amount.value:
            if not self.app.show_message("تحذير", f"رصيد الصندوق غير كافٍ (الرصيد: {box['balance']:.2f}). هل تريد المتابعة؟", "question"):
                return
        receipt = Receipt(receipt_type="صرف", receipt_date=self.payment_date.value, amount=float(self.amount.value),
                          payment_method=self.payment_method.value, notes=self.notes.value,
                          created_by=self.app.current_user, box_id=box_id, status="posted")
        rid, rno = self.repo.add_receipt(receipt)
        self.repo.update_cashbox_balance(box_id, -receipt.amount)
        self.load_payments(); self.amount.value = 0.0; self.notes.value = ""
        self.app.show_message("نجاح", f"تم حفظ سند الصرف برقم {rno}", "info")
    
    def print_receipt(self):
        if self.selected_receipt_no:
            receipt = self.repo.get_receipt_by_no(self.selected_receipt_no)
            if receipt: self._print_receipt_pdf(receipt)
    
    def print_payment(self):
        if self.selected_payment_no:
            receipt = self.repo.get_receipt_by_no(self.selected_payment_no)
            if receipt: self._print_receipt_pdf(receipt)
    
    def _print_receipt_pdf(self, receipt):
        company = self.repo.get_setting('company_name', 'جوهرة تعز مول')
        pdf = CustomPDF(company_name=company)
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, f"سند {receipt['receipt_type']} رقم: {receipt['receipt_no']}", 0, 1, 'C')
        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 10, f"التاريخ: {receipt['receipt_date']}", 0, 1, 'R')
        pdf.cell(0, 10, f"المبلغ: {receipt['amount']:.2f} ريال", 0, 1, 'R')
        pdf.cell(0, 10, f"طريقة الدفع: {receipt['payment_method']}", 0, 1, 'R')
        if receipt.get('revenue_type'): pdf.cell(0, 10, f"نوع الإيراد: {receipt['revenue_type']}", 0, 1, 'R')
        pdf.cell(0, 10, f"البيان: {receipt['notes'] or ''}", 0, 1, 'R')
        pdf.cell(0, 10, "المستلم: _________________", 0, 1, 'L')
        pdf.cell(0, 10, "المدير المالي: باسم فتح حقيس", 0, 1, 'L')
        fname = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=f"{receipt['receipt_type']}_{receipt['receipt_no']}.pdf")
        if fname: pdf.output(fname); self.app.show_message("نجاح", "تمت الطباعة", "info")

class RequirementsViewModel(ViewModelBase):
    def __init__(self, app):
        super().__init__(app)
        self.repo = app.repository
        self.requirements = Observable([])
        self.load_command = Command(self.load_requirements)
        self.update_status_command = Command(self.update_status)
        self.load_requirements()
    
    def load_requirements(self):
        self.requirements.value = self.repo.get_all_requirements()
    
    def update_status(self, req_id, new_status):
        self.repo.update_requirement_status(req_id, new_status)
        self.load_requirements()
        self.app.show_message("نجاح", "تم تحديث حالة الاحتياج", "info")

# ----------------------------- العرض (Views) -----------------------------
class BaseView(ctk.CTkFrame):
    def __init__(self, parent, view_model):
        super().__init__(parent)
        self.view_model = view_model
        self.setup_ui()
        self.bind_view_model()
    
    def setup_ui(self): pass
    def bind_view_model(self): pass
    
    def bind_text(self, observable, widget, attr='text'):
        def update(value):
            if attr == 'text': widget.configure(text=str(value))
            elif attr == 'variable' and hasattr(widget, 'set'): widget.set(str(value))
        observable.bind(update)
    
    def bind_entry(self, observable, entry_widget):
        def update(value):
            entry_widget.delete(0, tk.END); entry_widget.insert(0, str(value))
        observable.bind(update)
        def on_change(event=None): observable.value = entry_widget.get()
        entry_widget.bind('<KeyRelease>', on_change)
    
    def bind_combobox(self, observable, combo_widget):
        def update(value): combo_widget.set(str(value))
        observable.bind(update)
        def on_select(event=None): observable.value = combo_widget.get()
        combo_widget.bind('<<ComboboxSelected>>', on_select)
    
    def create_label(self, parent, text, **kwargs): return ctk.CTkLabel(parent, text=text, **kwargs)
    def create_entry(self, parent, width=200, **kwargs): return ctk.CTkEntry(parent, width=width, justify="right", **kwargs)
    def create_combobox(self, parent, values, width=200): return ttk.Combobox(parent, values=values, state='readonly', justify="right", width=width)
    
    def create_treeview(self, parent, columns, height=15):
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="both", expand=True, padx=5, pady=5)
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=height)
        for col in columns: tree.heading(col, text=col); tree.column(col, width=100, anchor="e")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        return tree

class TenantsView(BaseView):
    def setup_ui(self):
        self.create_label(self, "👥 إدارة المستأجرين", font=("Arial", 18, "bold"), anchor="center").pack(pady=20)
        form_frame = ctk.CTkFrame(self); form_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(form_frame, text="➕ إضافة مستأجر جديد", font=("Arial", 14, "bold")).pack(pady=5)
        inner = ctk.CTkFrame(form_frame); inner.pack(fill="x", padx=10, pady=10)
        self.shop_entry = self.create_entry(inner, width=150)
        self.name_entry = self.create_entry(inner, width=200)
        self.phone_entry = self.create_entry(inner, width=150)
        self.whatsapp_entry = self.create_entry(inner, width=150)
        self.rent_entry = self.create_entry(inner, width=120)
        self.rent_start_entry = self.create_entry(inner, width=120)
        self.contract_end_entry = self.create_entry(inner, width=120)
        fields = [("رقم المحل:", self.shop_entry), ("الاسم:", self.name_entry),
                  ("الهاتف:", self.phone_entry), ("واتساب:", self.whatsapp_entry),
                  ("الإيجار:", self.rent_entry), ("تاريخ بدء الإيجار:", self.rent_start_entry),
                  ("تاريخ انتهاء العقد:", self.contract_end_entry)]
        for i in range(0, len(fields), 2):
            row = ctk.CTkFrame(inner); row.pack(fill="x", pady=5)
            for j in range(2):
                if i+j < len(fields):
                    label, entry = fields[i+j]
                    ctk.CTkLabel(row, text=label, width=140, anchor="e").pack(side="left", padx=5)
                    entry.pack(side="left", padx=5)
        self.add_btn = ctk.CTkButton(inner, text="➕ إضافة", fg_color="green"); self.add_btn.pack(pady=10)
        btn_frame = ctk.CTkFrame(self); btn_frame.pack(fill="x", padx=10, pady=5)
        self.edit_btn = ctk.CTkButton(btn_frame, text="✏️ تعديل", fg_color="blue"); self.edit_btn.pack(side="left", padx=5)
        self.delete_btn = ctk.CTkButton(btn_frame, text="🗑️ حذف", fg_color="red"); self.delete_btn.pack(side="left", padx=5)
        self.export_btn = ctk.CTkButton(btn_frame, text="📊 تصدير Excel", fg_color="green"); self.export_btn.pack(side="left", padx=5)
        self.import_btn = ctk.CTkButton(btn_frame, text="📥 استيراد Excel", fg_color="blue"); self.import_btn.pack(side="left", padx=5)
        self.template_btn = ctk.CTkButton(btn_frame, text="📄 نموذج Excel", fg_color="orange"); self.template_btn.pack(side="left", padx=5)
        columns = ("id","shop","name","phone","whatsapp","rent","rent_start_date","rent_balance","active")
        self.tree = self.create_treeview(self, columns, height=15)
    
    def bind_view_model(self):
        vm = self.view_model
        self.bind_entry(vm.shop, self.shop_entry); self.bind_entry(vm.name, self.name_entry)
        self.bind_entry(vm.phone, self.phone_entry); self.bind_entry(vm.whatsapp, self.whatsapp_entry)
        self.bind_entry(vm.rent, self.rent_entry); self.bind_entry(vm.rent_start_date, self.rent_start_entry)
        self.bind_entry(vm.contract_end, self.contract_end_entry)
        self.add_btn.configure(command=vm.add_tenant_command.execute)
        self.edit_btn.configure(command=vm.update_tenant_command.execute)
        self.delete_btn.configure(command=vm.delete_tenant_command.execute)
        self.export_btn.configure(command=vm.export_excel_command.execute)
        self.import_btn.configure(command=vm.import_excel_command.execute)
        self.template_btn.configure(command=vm.export_template_command.execute)
        def update_tree(tenants):
            for row in self.tree.get_children(): self.tree.delete(row)
            for t in tenants:
                balance = t['rent_credit'] - t['rent_debit']
                self.tree.insert("", "end", iid=str(t['id']), values=(t['id'], t['shop'], t['name'], t['phone'] or '', t['whatsapp'] or '',
                                      f"{t['rent']:.2f}", t['rent_start_date'] or '', f"{balance:.2f}", "نشط"))
        vm.tenants.bind(update_tree)
        def on_select(event):
            sel = self.tree.selection()
            if sel:
                tid = int(sel[0])
                for t in vm.tenants.value:
                    if t['id'] == tid: vm.set_selected_tenant(t); break
        self.tree.bind('<<TreeviewSelect>>', on_select)

class ServicesView(BaseView):
    def setup_ui(self):
        self.create_label(self, "🔌 إدارة الخدمات", font=("Arial", 18, "bold"), anchor="center").pack(pady=20)
        form_frame = ctk.CTkFrame(self); form_frame.pack(fill="x", padx=10, pady=10)
        inner = ctk.CTkFrame(form_frame); inner.pack(fill="x", padx=10, pady=10)
        self.name_entry = self.create_entry(inner, width=200)
        self.unit_entry = self.create_entry(inner, width=120)
        self.monthly_entry = self.create_entry(inner, width=120)
        self.days_entry = self.create_entry(inner, width=200)
        ctk.CTkLabel(inner, text="اسم الخدمة:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.name_entry.grid(row=0, column=1, padx=5, pady=5)
        ctk.CTkLabel(inner, text="سعر الوحدة:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.unit_entry.grid(row=0, column=3, padx=5, pady=5)
        ctk.CTkLabel(inner, text="الرسوم الشهرية:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.monthly_entry.grid(row=1, column=1, padx=5, pady=5)
        ctk.CTkLabel(inner, text="أيام الفوترة:").grid(row=1, column=2, padx=5, pady=5, sticky="e")
        self.days_entry.grid(row=1, column=3, padx=5, pady=5)
        self.add_btn = ctk.CTkButton(inner, text="➕ إضافة", fg_color="green"); self.add_btn.grid(row=2, column=0, columnspan=4, pady=10)
        btn_frame = ctk.CTkFrame(self); btn_frame.pack(fill="x", padx=10, pady=5)
        self.edit_btn = ctk.CTkButton(btn_frame, text="✏️ تعديل", fg_color="blue"); self.edit_btn.pack(side="left", padx=5)
        self.delete_btn = ctk.CTkButton(btn_frame, text="🗑️ حذف", fg_color="red"); self.delete_btn.pack(side="left", padx=5)
        self.toggle_btn = ctk.CTkButton(btn_frame, text="🔄 تفعيل/تعطيل", fg_color="orange"); self.toggle_btn.pack(side="left", padx=5)
        columns = ("id","name","unit_price","monthly_fee","is_active")
        self.tree = self.create_treeview(self, columns, height=15)
    
    def bind_view_model(self):
        vm = self.view_model
        self.bind_entry(vm.name, self.name_entry); self.bind_entry(vm.unit_price, self.unit_entry)
        self.bind_entry(vm.monthly_fee, self.monthly_entry); self.bind_entry(vm.billing_days, self.days_entry)
        self.add_btn.configure(command=vm.add_service_command.execute)
        self.edit_btn.configure(command=vm.update_service_command.execute)
        self.delete_btn.configure(command=vm.delete_service_command.execute)
        self.toggle_btn.configure(command=vm.toggle_service_command.execute)
        def update_tree(services):
            for row in self.tree.get_children(): self.tree.delete(row)
            for s in services:
                status = "نشط" if s['is_active'] else "غير نشط"
                self.tree.insert("", "end", iid=str(s['id']), values=(s['id'], s['name'], f"{s['unit_price']:.2f}", f"{s['monthly_fee']:.2f}", status))
        vm.services.bind(update_tree)
        def on_select(event):
            sel = self.tree.selection()
            if sel:
                sid = int(sel[0])
                for s in vm.services.value:
                    if s['id'] == sid: vm.set_selected_service(s); break
        self.tree.bind('<<TreeviewSelect>>', on_select)

class UnifiedReadingsView(BaseView):
    def setup_ui(self):
        self.create_label(self, "📊 قراءات الخدمات", font=("Arial", 18, "bold"), anchor="center").pack(pady=20)
        select_frame = ctk.CTkFrame(self); select_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(select_frame, text="نوع الخدمة:").pack(side="left", padx=5)
        self.service_combo = self.create_combobox(select_frame, ["كهرباء", "ماء"], width=120); self.service_combo.pack(side="left", padx=5)
        ctk.CTkLabel(select_frame, text="المستأجر:").pack(side="left", padx=5)
        self.tenant_combo = self.create_combobox(select_frame, [], width=250); self.tenant_combo.pack(side="left", padx=5)
        self.load_readings_btn = ctk.CTkButton(select_frame, text="عرض القراءات", fg_color="blue"); self.load_readings_btn.pack(side="left", padx=5)
        form_frame = ctk.CTkFrame(self); form_frame.pack(fill="x", padx=10, pady=10)
        inner = ctk.CTkFrame(form_frame); inner.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(inner, text="القراءة السابقة:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.prev_entry = self.create_entry(inner, width=120); self.prev_entry.grid(row=0, column=1, padx=5, pady=5)
        ctk.CTkLabel(inner, text="القراءة الحالية:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.curr_entry = self.create_entry(inner, width=120); self.curr_entry.grid(row=0, column=3, padx=5, pady=5)
        ctk.CTkLabel(inner, text="تاريخ القراءة:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.date_entry = self.create_entry(inner, width=120); self.date_entry.grid(row=1, column=1, padx=5, pady=5)
        self.add_btn = ctk.CTkButton(inner, text="➕ إضافة قراءة", fg_color="green"); self.add_btn.grid(row=2, column=0, columnspan=4, pady=10)
        self.export_btn = ctk.CTkButton(inner, text="📊 تصدير Excel", fg_color="green"); self.export_btn.grid(row=3, column=0, columnspan=4, pady=5)
        columns = ("id","shop","previous_read","current_read","consumption","amount","reading_date","due_date","paid")
        self.tree = self.create_treeview(self, columns, height=15)
    
    def bind_view_model(self):
        vm = self.view_model
        self.bind_combobox(vm.service_type, self.service_combo)
        self.bind_entry(vm.previous_read, self.prev_entry); self.bind_entry(vm.current_read, self.curr_entry)
        self.bind_entry(vm.reading_date, self.date_entry)
        self.add_btn.configure(command=vm.add_reading_command.execute)
        self.export_btn.configure(command=vm.export_excel_command.execute)
        self.load_readings_btn.configure(command=vm.load_readings_command.execute)
        def update_tenants(tenants):
            self.tenant_combo['values'] = [f"{t['id']} - {t['shop']} - {t['name']}" for t in tenants]
        vm.tenants.bind(update_tenants)
        def tenant_selected(event):
            val = self.tenant_combo.get()
            if val:
                tid = int(val.split(" - ")[0])
                for t in vm.tenants.value:
                    if t['id'] == tid: vm.selected_tenant.value = t; break
        self.tenant_combo.bind('<<ComboboxSelected>>', tenant_selected)
        def update_readings(readings):
            for row in self.tree.get_children(): self.tree.delete(row)
            for r in readings:
                self.tree.insert("", "end", values=(r['id'], vm.selected_tenant.value['shop'] if vm.selected_tenant.value else "",
                                                    r['previous_read'], r['current_read'], r['consumption'], f"{r['amount']:.2f}",
                                                    r['reading_date'], r['due_date'], "مدفوع" if r['paid'] else "غير مدفوع"))
        vm.readings.bind(update_readings)
        vm.load_tenants_command.execute()

class CashboxesView(BaseView):
    def setup_ui(self):
        self.create_label(self, "💰 إدارة الصناديق", font=("Arial", 18, "bold"), anchor="center").pack(pady=20)
        form_frame = ctk.CTkFrame(self); form_frame.pack(fill="x", padx=10, pady=10)
        inner = ctk.CTkFrame(form_frame); inner.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(inner, text="اسم الصندوق:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.name_entry = self.create_entry(inner, width=200); self.name_entry.grid(row=0, column=1, padx=5, pady=5)
        ctk.CTkLabel(inner, text="النوع:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.type_combo = self.create_combobox(inner, ["عام","كهرباء","إيجارات","ماء"], width=120); self.type_combo.grid(row=0, column=3, padx=5, pady=5)
        ctk.CTkLabel(inner, text="الرصيد الافتتاحي:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.balance_entry = self.create_entry(inner, width=120); self.balance_entry.grid(row=1, column=1, padx=5, pady=5)
        self.add_btn = ctk.CTkButton(inner, text="➕ إضافة", fg_color="green"); self.add_btn.grid(row=2, column=0, columnspan=4, pady=10)
        columns = ("id","name","box_type","balance","active")
        self.tree = self.create_treeview(self, columns, height=15)
    
    def bind_view_model(self):
        vm = self.view_model
        self.bind_entry(vm.name, self.name_entry); self.bind_combobox(vm.box_type, self.type_combo)
        self.bind_entry(vm.balance, self.balance_entry)
        self.add_btn.configure(command=vm.add_command.execute)
        def update_tree(boxes):
            for row in self.tree.get_children(): self.tree.delete(row)
            for b in boxes: self.tree.insert("", "end", values=(b['id'], b['name'], b['box_type'], f"{b['balance']:.2f}", "نشط"))
        vm.cashboxes.bind(update_tree)
        vm.load_command.execute()

class ReceiptsView(BaseView):
    def setup_ui(self):
        self.notebook = ttk.Notebook(self); self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        self.receipt_tab = ctk.CTkFrame(self.notebook); self.notebook.add(self.receipt_tab, text="💰 سند قبض")
        self.payment_tab = ctk.CTkFrame(self.notebook); self.notebook.add(self.payment_tab, text="💸 سند صرف")
        self.setup_receipt_tab(); self.setup_payment_tab()
    
    def setup_receipt_tab(self):
        frame = ctk.CTkScrollableFrame(self.receipt_tab); frame.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(frame, text="تاريخ السند:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.receipt_date_entry = self.create_entry(frame, width=150); self.receipt_date_entry.grid(row=0, column=1, padx=5, pady=5)
        ctk.CTkLabel(frame, text="طريقة الدفع:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.receipt_method_combo = self.create_combobox(frame, ["نقدي","شيك","تحويل بنكي"], width=120); self.receipt_method_combo.grid(row=0, column=3, padx=5, pady=5)
        ctk.CTkLabel(frame, text="نوع الإيراد:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.revenue_combo = self.create_combobox(frame, ["إيجار","كهرباء","ماء","إيراد آخر"], width=120); self.revenue_combo.grid(row=1, column=1, padx=5, pady=5)
        ctk.CTkLabel(frame, text="المستأجر:").grid(row=1, column=2, padx=5, pady=5, sticky="e")
        self.tenant_combo = self.create_combobox(frame, [], width=200); self.tenant_combo.grid(row=1, column=3, padx=5, pady=5)
        ctk.CTkLabel(frame, text="المبلغ:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.amount_entry = self.create_entry(frame, width=150); self.amount_entry.grid(row=2, column=1, padx=5, pady=5)
        ctk.CTkLabel(frame, text="بالتفقيط:").grid(row=2, column=2, padx=5, pady=5, sticky="e")
        self.words_label = ctk.CTkLabel(frame, text="", width=250); self.words_label.grid(row=2, column=3, padx=5, pady=5)
        ctk.CTkLabel(frame, text="البيان:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.notes_entry = self.create_entry(frame, width=400); self.notes_entry.grid(row=3, column=1, columnspan=3, padx=5, pady=5)
        self.save_receipt_btn = ctk.CTkButton(frame, text="💾 حفظ وترحيل", fg_color="green"); self.save_receipt_btn.grid(row=4, column=0, columnspan=4, pady=10)
        self.print_receipt_btn = ctk.CTkButton(frame, text="🖨️ طباعة", fg_color="orange"); self.print_receipt_btn.grid(row=5, column=0, columnspan=4, pady=5)
        columns = ("receipt_no","receipt_date","amount","payment_method","revenue_type","notes","status")
        self.receipt_tree = self.create_treeview(self.receipt_tab, columns, height=10)
    
    def setup_payment_tab(self):
        frame = ctk.CTkScrollableFrame(self.payment_tab); frame.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(frame, text="تاريخ السند:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.payment_date_entry = self.create_entry(frame, width=150); self.payment_date_entry.grid(row=0, column=1, padx=5, pady=5)
        ctk.CTkLabel(frame, text="طريقة الدفع:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.payment_method_combo = self.create_combobox(frame, ["نقدي","شيك","تحويل بنكي"], width=120); self.payment_method_combo.grid(row=0, column=3, padx=5, pady=5)
        ctk.CTkLabel(frame, text="الصندوق:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.box_combo = self.create_combobox(frame, [], width=200); self.box_combo.grid(row=1, column=1, padx=5, pady=5)
        ctk.CTkLabel(frame, text="المبلغ:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.payment_amount_entry = self.create_entry(frame, width=150); self.payment_amount_entry.grid(row=2, column=1, padx=5, pady=5)
        ctk.CTkLabel(frame, text="بالتفقيط:").grid(row=2, column=2, padx=5, pady=5, sticky="e")
        self.payment_words_label = ctk.CTkLabel(frame, text="", width=250); self.payment_words_label.grid(row=2, column=3, padx=5, pady=5)
        ctk.CTkLabel(frame, text="البيان:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.payment_notes_entry = self.create_entry(frame, width=400); self.payment_notes_entry.grid(row=3, column=1, columnspan=3, padx=5, pady=5)
        self.save_payment_btn = ctk.CTkButton(frame, text="💾 حفظ وترحيل", fg_color="green"); self.save_payment_btn.grid(row=4, column=0, columnspan=4, pady=10)
        self.print_payment_btn = ctk.CTkButton(frame, text="🖨️ طباعة", fg_color="orange"); self.print_payment_btn.grid(row=5, column=0, columnspan=4, pady=5)
        columns = ("receipt_no","receipt_date","amount","payment_method","box_name","notes","status")
        self.payment_tree = self.create_treeview(self.payment_tab, columns, height=10)
    
    def bind_view_model(self):
        vm = self.view_model
        self.bind_entry(vm.receipt_date, self.receipt_date_entry); self.bind_entry(vm.payment_date, self.payment_date_entry)
        self.bind_entry(vm.amount, self.amount_entry); self.bind_entry(vm.amount, self.payment_amount_entry)
        self.bind_combobox(vm.payment_method, self.receipt_method_combo); self.bind_combobox(vm.payment_method, self.payment_method_combo)
        self.bind_combobox(vm.revenue_type, self.revenue_combo)
        self.bind_entry(vm.notes, self.notes_entry); self.bind_entry(vm.notes, self.payment_notes_entry)
        vm.amount.bind(lambda _: vm.update_amount_words())
        vm.amount_words.bind(lambda words: (self.words_label.configure(text=words), self.payment_words_label.configure(text=words)))
        self.save_receipt_btn.configure(command=vm.save_receipt_command.execute)
        self.save_payment_btn.configure(command=vm.save_payment_command.execute)
        self.print_receipt_btn.configure(command=vm.print_receipt_command.execute)
        self.print_payment_btn.configure(command=vm.print_payment_command.execute)
        def update_tenants(items): self.tenant_combo['values'] = [f"{tid} - {name}" for tid, name in items]
        vm.tenants_list.bind(update_tenants)
        def update_boxes(items): self.box_combo['values'] = [f"{bid} - {name}" for bid, name in items]
        vm.boxes_list.bind(update_boxes)
        def on_tenant_select(event):
            val = self.tenant_combo.get()
            if val: vm.selected_tenant_id.value = int(val.split(" - ")[0])
        self.tenant_combo.bind('<<ComboboxSelected>>', on_tenant_select)
        def on_box_select(event):
            val = self.box_combo.get()
            if val: vm.selected_box_id.value = int(val.split(" - ")[0])
        self.box_combo.bind('<<ComboboxSelected>>', on_box_select)
        def update_receipt_tree(receipts):
            for row in self.receipt_tree.get_children(): self.receipt_tree.delete(row)
            for r in receipts: self.receipt_tree.insert("", "end", values=(r['receipt_no'], r['receipt_date'], f"{r['amount']:.2f}",
                                                                          r['payment_method'], r['revenue_type'] or '', r['notes'] or '', r['status']))
        vm.receipts.bind(update_receipt_tree)
        def update_payment_tree(payments):
            for row in self.payment_tree.get_children(): self.payment_tree.delete(row)
            for p in payments:
                box_name = ""
                if p.get('box_id'):
                    box = vm.repo._execute("SELECT name FROM cashboxes WHERE id=?", (p['box_id'],), fetchone=True)
                    if box: box_name = box['name']
                self.payment_tree.insert("", "end", values=(p['receipt_no'], p['receipt_date'], f"{p['amount']:.2f}",
                                                            p['payment_method'], box_name, p['notes'] or '', p['status']))
        vm.payments.bind(update_payment_tree)
        def on_receipt_select(event):
            sel = self.receipt_tree.selection()
            if sel: vm.selected_receipt_no = self.receipt_tree.item(sel[0])['values'][0]
        self.receipt_tree.bind('<<TreeviewSelect>>', on_receipt_select)
        def on_payment_select(event):
            sel = self.payment_tree.selection()
            if sel: vm.selected_payment_no = self.payment_tree.item(sel[0])['values'][0]
        self.payment_tree.bind('<<TreeviewSelect>>', on_payment_select)
        vm.load_tenants(); vm.load_boxes(); vm.load_receipts_command.execute(); vm.load_payments_command.execute()

class RequirementsView(BaseView):
    def setup_ui(self):
        self.create_label(self, "📋 قائمة الاحتياجات الاحترافية للنظام", font=("Arial", 18, "bold"), anchor="center").pack(pady=20)
        info_frame = ctk.CTkFrame(self); info_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(info_frame, text="هذه القائمة تمثل التحديثات المطلوبة ليصبح النظام احترافياً. يمكنك تحديث حالة كل احتياج.",
                     font=("Arial", 12), anchor="center").pack(pady=5)
        columns = ("id","title","description","category","priority","status")
        self.tree = self.create_treeview(self, columns, height=20)
        self.tree.column("id", width=50, anchor="center")
        self.tree.column("title", width=200, anchor="e")
        self.tree.column("description", width=400, anchor="e")
        self.tree.column("category", width=120, anchor="center")
        self.tree.column("priority", width=80, anchor="center")
        self.tree.column("status", width=120, anchor="center")
        control_frame = ctk.CTkFrame(self); control_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(control_frame, text="تغيير حالة الاحتياج المحدد إلى:").pack(side="left", padx=5)
        self.status_combo = self.create_combobox(control_frame, ["planned","in_progress","completed","deferred"], width=150)
        self.status_combo.pack(side="left", padx=5)
        self.update_btn = ctk.CTkButton(control_frame, text="تحديث الحالة", fg_color="orange")
        self.update_btn.pack(side="left", padx=5)
        self.status_labels = {"planned":"📋 مخطط","in_progress":"⚙️ قيد التنفيذ","completed":"✅ منجز","deferred":"⏸️ مؤجل"}
    
    def bind_view_model(self):
        vm = self.view_model
        self.update_btn.configure(command=self.update_selected)
        def update_tree(requirements):
            for row in self.tree.get_children(): self.tree.delete(row)
            for r in requirements:
                priority_str = "عالي" if r['priority'] == 1 else "متوسط" if r['priority'] == 2 else "منخفض"
                status_display = self.status_labels.get(r['status'], r['status'])
                self.tree.insert("", "end", iid=str(r['id']), values=(r['id'], r['title'], r['description'], r['category'], priority_str, status_display))
        vm.requirements.bind(update_tree)
        vm.load_command.execute()
    
    def update_selected(self):
        selected = self.tree.selection()
        if not selected:
            self.view_model.app.show_message("تنبيه", "اختر احتياجاً أولاً", "warning")
            return
        req_id = int(selected[0])
        new_status = self.status_combo.get()
        if not new_status: return
        valid_statuses = ["planned","in_progress","completed","deferred"]
        if new_status not in valid_statuses:
            rev_map = {v: k for k, v in self.status_labels.items()}
            if new_status in rev_map: new_status = rev_map[new_status]
            else:
                self.view_model.app.show_message("خطأ", "حالة غير صالحة", "error")
                return
        self.view_model.update_status_command.execute(req_id, new_status)

# ----------------------------- التطبيق الرئيسي -----------------------------
class JawharaERPApp:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("💎 جوهرة تعز مول | النظام المحاسبي المتكامل MVVM")
        self.root.geometry("1400x800")
        ctk.set_appearance_mode("dark")
        self.repository = Repository(DB_PATH)
        self.current_user = None
        self.user_fullname = ""
        self.user_role = ""
        self.settings = {}
        self.load_settings()
        self.show_login()
    
    def load_settings(self):
        self.settings['company_name'] = self.repository.get_setting('company_name', 'جوهرة تعز مول')
    
    def show_message(self, title, message, msg_type="info"):
        if msg_type == "info": messagebox.showinfo(title, message)
        elif msg_type == "warning": messagebox.showwarning(title, message)
        elif msg_type == "error": messagebox.showerror(title, message)
        elif msg_type == "question": return messagebox.askyesno(title, message)
        return False
    
    def show_login(self):
        self.login_frame = ctk.CTkFrame(self.root)
        self.login_frame.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(self.login_frame, text="💎 جوهرة تعز", font=("Arial", 28, "bold")).pack(pady=20)
        ctk.CTkLabel(self.login_frame, text="تسجيل الدخول").pack(pady=10)
        self.username_entry = ctk.CTkEntry(self.login_frame, width=200, justify="right")
        self.username_entry.pack(pady=5)
        self.username_entry.insert(0, "admin")
        self.password_entry = ctk.CTkEntry(self.login_frame, width=200, show="*", justify="right")
        self.password_entry.pack(pady=5)
        self.password_entry.insert(0, "basem2026")
        ctk.CTkButton(self.login_frame, text="دخول", command=self.do_login, fg_color="green", width=150).pack(pady=20)
        self.password_entry.bind("<Return>", lambda e: self.do_login())
    
    def do_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        user = self.repository.authenticate_user(username, password)
        if user:
            self.current_user = user['username']
            self.user_fullname = user['full_name']
            self.user_role = user['role']
            self.login_frame.destroy()
            self.show_main()
        else:
            self.show_message("خطأ", "اسم مستخدم أو كلمة مرور غير صحيحة", "error")
    
    def show_main(self):
        self.tenants_vm = TenantsViewModel(self)
        self.services_vm = ServicesViewModel(self)
        self.readings_vm = UnifiedReadingsViewModel(self)
        self.cashboxes_vm = CashboxesViewModel(self)
        self.receipts_vm = ReceiptsViewModel(self)
        self.requirements_vm = RequirementsViewModel(self)
        self.create_header()
        self.create_sidebar()
        self.workspace = ctk.CTkFrame(self.root)
        self.workspace.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        self.show_dashboard()
    
    def create_header(self):
        header = ctk.CTkFrame(self.root, height=60, fg_color="gray20")
        header.pack(fill="x")
        ctk.CTkLabel(header, text=self.settings.get('company_name', 'جوهرة تعز'), font=("Arial", 16, "bold")).pack(side="right", padx=20)
        ctk.CTkLabel(header, text=f"👤 {self.user_fullname} ({self.user_role})").pack(side="left", padx=20)
        ctk.CTkButton(header, text="❌ خروج", command=self.logout, fg_color="transparent", hover_color="gray30").pack(side="left", padx=5)
    
    def create_sidebar(self):
        sidebar = ctk.CTkFrame(self.root, width=220, fg_color="gray20")
        sidebar.pack(side="right", fill="y")
        sidebar.pack_propagate(False)
        items = [
            ("📊 لوحة التحكم", self.show_dashboard),
            ("👥 المستأجرين", self.show_tenants),
            ("🔌 الخدمات", self.show_services),
            ("📊 قراءات الخدمات", self.show_readings),
            ("💰 الصناديق", self.show_cashboxes),
            ("💰 سندات القبض/الصرف", self.show_receipts),
            ("📋 قائمة الاحتياجات", self.show_requirements),
            ("📋 التقارير", self.show_reports),
            ("⚙️ الإعدادات", self.show_settings),
        ]
        for text, cmd in items:
            btn = ctk.CTkButton(sidebar, text=text, command=cmd, fg_color="transparent", hover_color="gray30", anchor="w", height=35)
            btn.pack(fill="x", padx=5, pady=2)
    
    def clear_workspace(self):
        for w in self.workspace.winfo_children(): w.destroy()
    
    def show_dashboard(self):
        self.clear_workspace()
        stats = self.repository.get_dashboard_stats()
        chart_data = self.repository.get_chart_data()
        frame = ctk.CTkFrame(self.workspace); frame.pack(fill="both", expand=True)
        ctk.CTkLabel(frame, text="📊 لوحة التحكم", font=("Arial", 20, "bold")).pack(pady=20)
        cards_frame = ctk.CTkFrame(frame); cards_frame.pack(pady=20)
        cards = [
            ("👥 المستأجرين", stats['total_tenants']),
            ("💰 إيرادات الإيجار", f"{stats['rent_revenue']:,.0f} ريال"),
            ("⚡ إيرادات الكهرباء", f"{stats['electricity_revenue']:,.0f} ريال"),
            ("💧 إيرادات الماء", f"{stats['water_revenue']:,.0f} ريال"),
            ("💸 المصروفات", f"{stats['total_expenses']:,.0f} ريال"),
            ("💵 إجمالي الصناديق", f"{stats['total_cash']:,.0f} ريال"),
            ("📉 مديونية الإيجار", f"{stats['total_rent_debt']:,.0f} ريال"),
        ]
        for i, (title, val) in enumerate(cards):
            card = ctk.CTkFrame(cards_frame, width=200, height=100, fg_color="gray25")
            card.grid(row=0, column=i, padx=10, pady=10)
            card.grid_propagate(False)
            ctk.CTkLabel(card, text=title, font=("Arial", 12)).pack(pady=10)
            ctk.CTkLabel(card, text=str(val), font=("Arial", 14, "bold")).pack()
        if chart_data:
            fig, ax = plt.subplots(figsize=(8,4))
            fig.patch.set_facecolor('#2c3e50'); ax.set_facecolor('#34495e')
            ax.tick_params(colors='white')
            months = [d['month'][-5:] for d in chart_data]
            rent = [d['rent'] for d in chart_data]; elec = [d['elec'] for d in chart_data]; water = [d['water'] for d in chart_data]
            ax.plot(months, rent, marker='o', label='إيجارات', color='#3498db')
            ax.plot(months, elec, marker='s', label='كهرباء', color='#f1c40f')
            ax.plot(months, water, marker='^', label='ماء', color='#1abc9c')
            ax.legend(prop={'family':'Arial'}); ax.grid(True, alpha=0.3); ax.set_title('الإيرادات الشهرية', fontname='Arial')
            canvas = FigureCanvasTkAgg(fig, master=frame); canvas.draw(); canvas.get_tk_widget().pack(pady=20)
    
    def show_tenants(self): self.clear_workspace(); TenantsView(self.workspace, self.tenants_vm).pack(fill="both", expand=True)
    def show_services(self): self.clear_workspace(); ServicesView(self.workspace, self.services_vm).pack(fill="both", expand=True)
    def show_readings(self): self.clear_workspace(); UnifiedReadingsView(self.workspace, self.readings_vm).pack(fill="both", expand=True)
    def show_cashboxes(self): self.clear_workspace(); CashboxesView(self.workspace, self.cashboxes_vm).pack(fill="both", expand=True)
    def show_receipts(self): self.clear_workspace(); ReceiptsView(self.workspace, self.receipts_vm).pack(fill="both", expand=True)
    def show_requirements(self): self.clear_workspace(); RequirementsView(self.workspace, self.requirements_vm).pack(fill="both", expand=True)
    
    def show_reports(self):
        self.clear_workspace()
        frame = ctk.CTkFrame(self.workspace); frame.pack(fill="both", expand=True)
        ctk.CTkLabel(frame, text="📋 التقارير", font=("Arial", 18, "bold")).pack(pady=20)
        def rep_tenants():
            data = self.repository.get_all_tenants()
            cols = ["المحل","الاسم","الهاتف","الرصيد"]
            rows = [(t['shop'], t['name'], t['phone'], t['rent_credit'] - t['rent_debit']) for t in data]
            self.show_report_dialog("تقرير المستأجرين", cols, rows)
        def rep_receipts():
            data = self.repository.get_receipts('قبض')
            cols = ["رقم السند","التاريخ","المبلغ","طريقة الدفع","نوع الإيراد","البيان"]
            rows = [(r['receipt_no'], r['receipt_date'], r['amount'], r['payment_method'], r['revenue_type'] or '', r['notes'] or '') for r in data]
            self.show_report_dialog("تقرير سندات القبض", cols, rows)
        ctk.CTkButton(frame, text="تقرير المستأجرين", command=rep_tenants, fg_color="blue").pack(pady=5)
        ctk.CTkButton(frame, text="تقرير سندات القبض", command=rep_receipts, fg_color="blue").pack(pady=5)
    
    def show_report_dialog(self, title, columns, data):
        win = ctk.CTkToplevel(self.root); win.title(title); win.geometry("800x500")
        frame = ctk.CTkFrame(win); frame.pack(fill="both", expand=True, padx=10, pady=10)
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        for col in columns: tree.heading(col, text=col); tree.column(col, width=100, anchor="e")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True); vsb.pack(side="right", fill="y")
        for row in data: tree.insert("", "end", values=row)
        ctk.CTkButton(win, text="إغلاق", command=win.destroy).pack(pady=10)
    
    def show_settings(self):
        self.clear_workspace()
        frame = ctk.CTkFrame(self.workspace); frame.pack(fill="both", expand=True)
        ctk.CTkLabel(frame, text="⚙️ الإعدادات", font=("Arial", 18, "bold")).pack(pady=20)
        ctk.CTkLabel(frame, text="اسم الشركة:").pack()
        company_entry = ctk.CTkEntry(frame, width=300, justify="right")
        company_entry.pack(pady=5)
        company_entry.insert(0, self.settings.get('company_name', ''))
        def save():
            new_name = company_entry.get()
            self.repository.set_setting('company_name', new_name)
            self.settings['company_name'] = new_name
            self.show_message("نجاح", "تم حفظ الإعدادات", "info")
        ctk.CTkButton(frame, text="💾 حفظ", command=save, fg_color="green").pack(pady=20)
    
    def logout(self):
        if self.show_message("تأكيد", "هل تريد تسجيل الخروج؟", "question"):
            self.root.destroy()
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = JawharaERPApp()
    app.run()