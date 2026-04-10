# 🚀 Zenith_B | Smart ERP Management System

**Zenith_B** هو نظام محاسبي وإداري متطور، يمثل القمة في حلول إدارة المجمعات التجارية (المولات) والعقارات. تم بناء النظام باستخدام لغة **Python** مع اتباع نمط المعمارية العالمي **MVVM** (Model-View-ViewModel) لضمان استقرار العمليات وسهولة التوسع المستقبلي.

---

## ✨ ميزات إصدار Zenith_B المطوّر

لقد تم دمج 5 تحديثات جوهرية في هذا الإصدار لتعزيز كفاءة الإدارة:

1.  **🛡️ Zenith Security (نظام الصلاحيات):** إدارة دخول المستخدمين وتحديد الأدوار (Admin vs User) لحماية البيانات المالية الحساسة.
2.  **🔔 Zenith Alerts (التنبيهات الذكية):** فحص تلقائي لعقود الإيجار المنتهية والمديونيات المتأخرة عند تشغيل النظام.
3.  **💬 Zenith WhatsApp Link:** إمكانية إرسال تقارير السداد والسندات مباشرة للمستأجرين عبر WhatsApp.
4.  **📊 Zenith Insights (لوحة البيانات):** داشبورد تفاعلية تعرض رسوماً بيانية فورية للإيرادات والمصروفات ونسب الإشغال.
5.  **💾 Zenith Safe-Vault (الأرشفة الذكية):** نظام نسخ احتياطي تلقائي لقاعدة البيانات (Auto-Backup) لضمان عدم ضياع البيانات تحت أي ظرف.

---

## 🛠 التكنولوجيات المستخدمة (Tech Stack)

* **GUI:** [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) لواجهة مستخدم حديثة تدعم الوضع الليلي.
* **Database:** SQLite3 مع معالجة SQL المتقدمة.
* **Data Analysis:** [Pandas](https://pandas.pydata.org/) لمعالجة البيانات الضخمة.
* **Visualization:** [Matplotlib](https://matplotlib.org/) لتوليد الرسوم البيانية.
* **Reporting:** FPDF لإنشاء فواتير وسندات احترافية بصيغة PDF.
* **Language Support:** مكتبات Arabic-Reshaper و Python-Bidi لدعم النصوص العربية بشكل صحيح.

---

## 🏗 بنية المشروع (Architecture)

يتبع المشروع نمط **MVVM** لضمان فصل المهام:
* **Model:** تمثيل البيانات والجداول (Tenants, Receipts, Services).
* **ViewModel:** معالجة العمليات المحاسبية ومنطق العمل (Business Logic).
* **View:** واجهة المستخدم التفاعلية التي ترتبط بالبيانات تلقائياً.

---

## ⚙️ التثبيت والتشغيل (Quick Start)

1. **تحميل المكتبات اللازمة:**
   ```bash
   pip install customtkinter pandas matplotlib fpdf arabic-reshaper python-bidi
