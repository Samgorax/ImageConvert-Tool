"""
ui/theme.py
===========
Application-wide QSS stylesheet and colour tokens.

Design system:
- Deep navy / near-black base (GitHub Dark-inspired)
- Deep purple accent (#7c3aed / #a78bfa)
- Semantic status colours: emerald success, amber warning, red error
- All colours defined in COLORS dict so any widget can programmatically
  reference them without parsing CSS strings.
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette

# ── Colour tokens ──────────────────────────────────────────────────────────────
COLORS: dict[str, str] = {
    "bg_primary":     "#0d1117",
    "bg_secondary":   "#101827",
    "bg_card":        "#151f31",
    "bg_hover":       "#202b40",
    "sidebar_bg":     "#080b17",
    "accent":         "#7c3aed",
    "accent_hover":   "#6d28d9",
    "accent_light":   "#a78bfa",
    "success":        "#10b981",
    "warning":        "#f59e0b",
    "error":          "#ef4444",
    "text_primary":   "#e6edf3",
    "text_secondary": "#8b949e",
    "text_muted":     "#484f58",
    "border":         "#30363d",
    "border_light":   "#21262d",
    "scrollbar":      "#21262d",
}

C = COLORS   # short alias used inside the stylesheet string


STYLESHEET = f"""
/* ══════════════════════════════════════════════════════════════════
   Global
   ══════════════════════════════════════════════════════════════════ */
* {{
    font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    color: {C['text_primary']};
    outline: none;
}}

QMainWindow, QDialog {{
    background-color: {C['bg_primary']};
}}

QWidget#workbench_sidebar {{
    background: qlineargradient(x1:0, y1:0, x2:0.8, y2:1,
        stop:0 #0b0d1c, stop:0.58 #090d1b, stop:1 #101329);
    border-right: 1px solid #252943;
}}

QWidget#workbench_main_area {{
    background-color: {C['bg_primary']};
}}

QScrollArea#dashboard_scroll, QWidget#dashboard_content {{
    background-color: transparent;
    border: none;
}}

QWidget#workbench_header {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #111827, stop:0.6 #101827, stop:1 #111329);
    border-bottom: 1px solid #262c42;
}}

QLabel#workbench_brand {{
    color: {C['text_primary']};
    font-size: 15px;
    font-weight: 800;
    letter-spacing: 0.5px;
    line-height: 1.1;
}}

QLabel#workbench_brand_mark {{
    color: white;
    font-size: 15px;
    font-weight: 800;
    border-radius: 13px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #8b5cf6, stop:1 #6425d5);
}}

QLabel#workbench_brand_subtitle {{
    color: #777f9f;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1px;
}}

QLabel#sidebar_section {{
    color: {C['text_muted']};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.2px;
}}

QPushButton#workbench_nav_button {{
    background-color: transparent;
    color: #a2a9c0;
    text-align: left;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 0 14px;
    font-size: 13px;
    font-weight: 600;
}}

QPushButton#workbench_nav_button:hover {{
    background-color: rgba(135, 94, 246, 0.11);
    color: {C['text_primary']};
}}

QPushButton#workbench_nav_button:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #7138df, stop:1 #5423bb);
    color: white;
    border: 1px solid rgba(190, 160, 255, 0.26);
}}

QLabel#sidebar_footer {{
    color: #a0a9c2;
    background-color: rgba(18, 25, 43, 0.86);
    border: 1px solid #252d47;
    border-radius: 10px;
    font-size: 11px;
    line-height: 1.5;
    padding: 12px 11px;
}}

QLabel#sidebar_developer_credit {{
    color: #78839e;
    font-size: 10px;
    padding: 3px 4px 8px;
}}

QLabel#workbench_page_title {{
    color: {C['text_primary']};
    font-size: 21px;
    font-weight: 750;
}}

QLabel#workbench_page_subtitle, QLabel#muted_text {{
    color: {C['text_secondary']};
    font-size: 12px;
}}

QLabel#workbench_mode_badge {{
    color: {C['warning']};
    background-color: rgba(245, 158, 11, 0.10);
    border: 1px solid rgba(245, 158, 11, 0.22);
    border-radius: 10px;
    padding: 6px 10px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.6px;
}}

QFrame#workbench_card {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #182338, stop:1 #121a2b);
    border: 1px solid #2a344b;
    border-radius: 14px;
}}

QFrame#dashboard_status_card, QFrame#dashboard_recent_row {{
    background-color: #121b2d;
    border: 1px solid #29344b;
    border-radius: 12px;
}}

QLabel#dashboard_card_heading {{
    color: #a8b2ca;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.4px;
}}

QLabel#dashboard_status_value {{
    color: {C['text_primary']};
    font-size: 15px;
    font-weight: 700;
}}

QLabel#dashboard_status_detail, QLabel#dashboard_recent_detail {{
    color: #9ba7c0;
    font-size: 11px;
}}

QLabel#dashboard_recent_name {{
    color: {C['text_primary']};
    font-size: 12px;
    font-weight: 600;
}}

QLabel#dashboard_section_title {{
    color: {C['text_primary']};
    font-size: 15px;
    font-weight: 700;
}}

QPushButton#dashboard_action {{
    color: {C['text_primary']};
    background-color: #1b2740;
    border: 1px solid #303d59;
    border-radius: 11px;
    padding: 11px 12px;
    text-align: left;
    font-size: 12px;
    font-weight: 650;
}}

QPushButton#dashboard_action:hover {{
    background-color: #253354;
    border-color: #7255bd;
}}

QPushButton#dashboard_action:focus {{
    border: 2px solid {C['accent_light']};
}}

QLabel#card_heading {{
    color: {C['text_primary']};
    font-size: 14px;
    font-weight: 700;
}}

QFrame#dashboard_hero {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #211a3c, stop:0.52 #171c32, stop:1 #121d30);
    border: 1px solid #423363;
    border-radius: 16px;
}}

QLabel#dashboard_hero_title {{
    color: #f2efff;
    font-size: 23px;
    font-weight: 750;
}}

QLabel#dashboard_hero_detail {{
    color: #b4bad0;
    font-size: 13px;
}}

QLabel#card_detail {{
    color: {C['text_secondary']};
    font-size: 12px;
    background-color: transparent;
}}

QLabel#card_heading, QLabel#muted_text, QLabel#workbench_page_title,
QLabel#workbench_page_subtitle, QLabel#dashboard_hero_title,
QLabel#dashboard_hero_detail, QLabel#dashboard_card_heading,
QLabel#dashboard_status_value, QLabel#dashboard_status_detail,
QLabel#dashboard_recent_name, QLabel#dashboard_recent_detail,
QLabel#dashboard_section_title {{
    background-color: transparent;
}}

QPushButton#primary_button {{
    background-color: {C['accent']};
    color: white;
    border: none;
    border-radius: 7px;
    padding: 8px 14px;
    font-weight: 600;
}}

QPushButton#primary_button:hover {{
    background-color: {C['accent_hover']};
}}

/* ══════════════════════════════════════════════════════════════════
   Sidebar
   ══════════════════════════════════════════════════════════════════ */
QWidget#sidebar {{
    background-color: {C['sidebar_bg']};
    border-right: 1px solid {C['border']};
    min-width: 68px;
    max-width: 68px;
}}

QPushButton#nav_btn {{
    background:   transparent;
    border:       none;
    border-radius: 10px;
    padding:      10px;
    color:        {C['text_secondary']};
    font-size:    22px;
    min-width:    44px;
    min-height:   44px;
    max-width:    44px;
    max-height:   44px;
    margin:       2px 12px;
}}

QPushButton#nav_btn:hover {{
    background-color: {C['bg_hover']};
    color: {C['text_primary']};
}}

QPushButton#nav_btn[active="true"] {{
    background-color: {C['accent']};
    color: white;
}}

/* ══════════════════════════════════════════════════════════════════
   Header bar
   ══════════════════════════════════════════════════════════════════ */
QWidget#header {{
    background-color: {C['bg_secondary']};
    border-bottom: 1px solid {C['border']};
    min-height: 56px;
    max-height: 56px;
}}

QLabel#app_title {{
    font-size: 15px;
    font-weight: 700;
    color: {C['text_primary']};
    letter-spacing: 0.3px;
}}

QLabel#panel_subtitle {{
    font-size: 12px;
    color: {C['text_secondary']};
}}

/* ══════════════════════════════════════════════════════════════════
   Cards / frames
   ══════════════════════════════════════════════════════════════════ */
QFrame#card {{
    background-color: {C['bg_card']};
    border: 1px solid {C['border']};
    border-radius: 12px;
}}

/* ══════════════════════════════════════════════════════════════════
   Drop zone
   ══════════════════════════════════════════════════════════════════ */
QFrame#drop_zone {{
    background-color: {C['bg_secondary']};
    border: 2px dashed {C['border']};
    border-radius: 16px;
    min-height: 130px;
}}

QFrame#drop_zone:hover {{
    border-color: {C['accent_light']};
    background-color: #13151f;
}}

QFrame#drop_zone[drag_active="true"] {{
    border-color: {C['accent']};
    background-color: rgba(124, 58, 237, 0.08);
}}

/* ══════════════════════════════════════════════════════════════════
   Format combo boxes
   ══════════════════════════════════════════════════════════════════ */
QComboBox#format_combo {{
    background-color: {C['bg_hover']};
    border: 1px solid {C['border']};
    border-radius: 8px;
    padding: 8px 36px 8px 14px;
    font-size: 14px;
    font-weight: 700;
    min-height: 42px;
    min-width: 130px;
    color: {C['text_primary']};
}}

QComboBox#format_combo:hover {{
    border-color: {C['accent_light']};
    background-color: #1e2430;
}}

QComboBox#format_combo:focus {{
    border-color: {C['accent']};
}}

QComboBox#format_combo::drop-down {{
    border: none;
    subcontrol-origin: padding;
    subcontrol-position: right center;
    width: 28px;
}}

QComboBox#format_combo::down-arrow {{
    border-left:  5px solid transparent;
    border-right: 5px solid transparent;
    border-top:   6px solid {C['text_secondary']};
    width: 0; height: 0;
}}

QComboBox QAbstractItemView {{
    background-color: {C['bg_card']};
    border: 1px solid {C['border']};
    border-radius: 8px;
    selection-background-color: {C['accent']};
    selection-color: white;
    padding: 4px;
    outline: none;
}}

QComboBox QAbstractItemView::item {{
    min-height: 30px;
    padding: 4px 12px;
    border-radius: 4px;
    color: {C['text_primary']};
}}

/* ══════════════════════════════════════════════════════════════════
   Buttons
   ══════════════════════════════════════════════════════════════════ */
QPushButton#primary_btn {{
    background-color: {C['accent']};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 28px;
    font-size: 14px;
    font-weight: 600;
    min-height: 42px;
    letter-spacing: 0.2px;
}}

QPushButton#primary_btn:hover {{
    background-color: {C['accent_hover']};
}}

QPushButton#primary_btn:pressed {{
    background-color: #5b21b6;
}}

QPushButton#primary_btn:disabled {{
    background-color: {C['text_muted']};
    color: {C['bg_hover']};
}}

QPushButton#secondary_btn {{
    background-color: transparent;
    color: {C['text_primary']};
    border: 1px solid {C['border']};
    border-radius: 8px;
    padding: 8px 18px;
    font-size: 13px;
    min-height: 38px;
}}

QPushButton#secondary_btn:hover {{
    background-color: {C['bg_hover']};
    border-color: {C['text_secondary']};
}}

QPushButton#secondary_btn:pressed {{
    background-color: {C['bg_card']};
}}

QPushButton#icon_btn {{
    background-color: transparent;
    border: 1px solid {C['border']};
    border-radius: 6px;
    padding: 5px 10px;
    color: {C['text_secondary']};
    font-size: 16px;
    min-height: 32px;
    min-width: 32px;
}}

QPushButton#icon_btn:hover {{
    background-color: {C['bg_hover']};
    color: {C['text_primary']};
}}

/* ══════════════════════════════════════════════════════════════════
   Progress bar
   ══════════════════════════════════════════════════════════════════ */
QProgressBar#conversion_progress {{
    background-color: {C['bg_secondary']};
    border: none;
    border-radius: 6px;
    height: 8px;
    text-align: center;
    color: transparent;
    font-size: 1px;
}}

QProgressBar#conversion_progress::chunk {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {C['accent']}, stop:1 {C['accent_light']}
    );
    border-radius: 6px;
}}

/* ══════════════════════════════════════════════════════════════════
   Sliders
   ══════════════════════════════════════════════════════════════════ */
QSlider::groove:horizontal {{
    background-color: {C['bg_hover']};
    height: 6px;
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background-color: {C['accent']};
    border: 2px solid {C['accent_light']};
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}}

QSlider::handle:horizontal:hover {{
    background-color: {C['accent_hover']};
}}

QSlider::sub-page:horizontal {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {C['accent']}, stop:1 {C['accent_light']}
    );
    border-radius: 3px;
}}

/* ══════════════════════════════════════════════════════════════════
   Tables
   ══════════════════════════════════════════════════════════════════ */
QTableWidget {{
    background-color: {C['bg_secondary']};
    alternate-background-color: {C['bg_card']};
    border: none;
    border-radius: 8px;
    gridline-color: {C['border_light']};
    selection-background-color: rgba(124, 58, 237, 0.25);
    selection-color: {C['text_primary']};
}}

QTableWidget::item {{
    padding: 8px 12px;
    border: none;
}}

QTableWidget::item:selected {{
    background-color: rgba(124, 58, 237, 0.25);
}}

QHeaderView::section {{
    background-color: {C['bg_primary']};
    color: {C['text_secondary']};
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    padding: 10px 12px;
    border: none;
    border-bottom: 1px solid {C['border']};
}}

QHeaderView::section:first {{
    border-top-left-radius: 8px;
}}

/* ══════════════════════════════════════════════════════════════════
   Scroll bars
   ══════════════════════════════════════════════════════════════════ */
QScrollBar:vertical {{
    background-color: transparent;
    width: 8px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: {C['scrollbar']};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {C['text_muted']};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 8px;
}}

QScrollBar::handle:horizontal {{
    background-color: {C['scrollbar']};
    border-radius: 4px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {C['text_muted']};
}}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ══════════════════════════════════════════════════════════════════
   Labels
   ══════════════════════════════════════════════════════════════════ */
QLabel#section_label {{
    font-size: 11px;
    font-weight: 700;
    color: {C['text_secondary']};
    letter-spacing: 0.8px;
}}

QLabel#drop_title {{
    font-size: 15px;
    font-weight: 600;
    color: {C['text_secondary']};
}}

QLabel#drop_sub {{
    font-size: 12px;
    color: {C['text_muted']};
}}

QLabel#status_ok {{
    color: {C['success']};
    background-color: rgba(16, 185, 129, 0.1);
    border-radius: 6px;
    padding: 3px 10px;
    font-weight: 600;
    font-size: 12px;
}}

QLabel#status_warn {{
    color: {C['warning']};
    background-color: rgba(245, 158, 11, 0.1);
    border-radius: 6px;
    padding: 3px 10px;
    font-weight: 600;
    font-size: 12px;
}}

QLabel#status_err {{
    color: {C['error']};
    background-color: rgba(239, 68, 68, 0.1);
    border-radius: 6px;
    padding: 3px 10px;
    font-weight: 600;
    font-size: 12px;
}}

QLabel#arrow_label {{
    font-size: 22px;
    color: {C['accent_light']};
    padding: 0 8px;
}}

/* ══════════════════════════════════════════════════════════════════
   Line edits
   ══════════════════════════════════════════════════════════════════ */
QLineEdit {{
    background-color: {C['bg_hover']};
    border: 1px solid {C['border']};
    border-radius: 8px;
    padding: 8px 12px;
    color: {C['text_primary']};
    font-size: 13px;
    min-height: 36px;
}}

QLineEdit:focus {{
    border-color: {C['accent_light']};
    background-color: {C['bg_secondary']};
}}

QLineEdit:read-only {{
    color: {C['text_secondary']};
    background-color: {C['bg_secondary']};
}}

QLineEdit::placeholder {{
    color: {C['text_muted']};
}}

/* ══════════════════════════════════════════════════════════════════
   Checkboxes
   ══════════════════════════════════════════════════════════════════ */
QCheckBox {{
    color: {C['text_primary']};
    spacing: 8px;
    font-size: 13px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {C['border']};
    border-radius: 4px;
    background-color: {C['bg_hover']};
}}

QCheckBox::indicator:checked {{
    background-color: {C['accent']};
    border-color: {C['accent']};
}}

QCheckBox::indicator:hover {{
    border-color: {C['accent_light']};
}}

/* ══════════════════════════════════════════════════════════════════
   Spin boxes
   ══════════════════════════════════════════════════════════════════ */
QSpinBox {{
    background-color: {C['bg_hover']};
    border: 1px solid {C['border']};
    border-radius: 8px;
    padding: 6px 10px;
    color: {C['text_primary']};
    min-height: 36px;
    min-width: 80px;
}}

QSpinBox:focus {{
    border-color: {C['accent_light']};
}}

QSpinBox::up-button, QSpinBox::down-button {{
    background-color: transparent;
    border: none;
    width: 22px;
}}

QSpinBox::up-arrow {{
    border-left:   4px solid transparent;
    border-right:  4px solid transparent;
    border-bottom: 5px solid {C['text_secondary']};
    width: 0; height: 0;
}}

QSpinBox::down-arrow {{
    border-left:  4px solid transparent;
    border-right: 4px solid transparent;
    border-top:   5px solid {C['text_secondary']};
    width: 0; height: 0;
}}

/* ══════════════════════════════════════════════════════════════════
   Group boxes
   ══════════════════════════════════════════════════════════════════ */
QGroupBox {{
    border: 1px solid {C['border']};
    border-radius: 10px;
    margin-top: 18px;
    padding-top: 10px;
    color: {C['text_secondary']};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.6px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    left: 14px;
    top: -1px;
    background-color: {C['bg_primary']};
    text-transform: uppercase;
}}

/* ══════════════════════════════════════════════════════════════════
   Status bar
   ══════════════════════════════════════════════════════════════════ */
QStatusBar {{
    background-color: {C['sidebar_bg']};
    color: {C['text_secondary']};
    border-top: 1px solid {C['border']};
    font-size: 12px;
    padding: 2px 10px;
}}

QStatusBar::item {{
    border: none;
}}

/* ══════════════════════════════════════════════════════════════════
   Tooltips
   ══════════════════════════════════════════════════════════════════ */
QToolTip {{
    background-color: {C['bg_card']};
    color: {C['text_primary']};
    border: 1px solid {C['border']};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* ══════════════════════════════════════════════════════════════════
   Message boxes
   ══════════════════════════════════════════════════════════════════ */
QMessageBox {{
    background-color: {C['bg_secondary']};
}}

QMessageBox QLabel {{
    color: {C['text_primary']};
    font-size: 13px;
}}

QMessageBox QPushButton {{
    background-color: {C['accent']};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 6px 22px;
    min-width: 80px;
    min-height: 32px;
    font-weight: 600;
}}

QMessageBox QPushButton:hover {{
    background-color: {C['accent_hover']};
}}

/* ══════════════════════════════════════════════════════════════════
   Tab widget (settings dialog)
   ══════════════════════════════════════════════════════════════════ */
QTabWidget::pane {{
    border: 1px solid {C['border']};
    border-radius: 8px;
    background-color: {C['bg_secondary']};
    top: -1px;
}}

QTabBar::tab {{
    background-color: transparent;
    color: {C['text_secondary']};
    padding: 8px 20px;
    border: none;
    font-size: 13px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    color: {C['accent_light']};
    border-bottom: 2px solid {C['accent']};
}}

QTabBar::tab:hover {{
    color: {C['text_primary']};
}}

/* ══════════════════════════════════════════════════════════════════
   Dialog button box
   ══════════════════════════════════════════════════════════════════ */
QDialogButtonBox QPushButton {{
    background-color: {C['accent']};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 6px 20px;
    min-width: 80px;
    min-height: 32px;
    font-weight: 600;
}}

QDialogButtonBox QPushButton:hover {{
    background-color: {C['accent_hover']};
}}
"""


def apply_theme(app) -> None:
    """Apply the dark stylesheet and palette to *app* (a QApplication)."""
    app.setStyleSheet(STYLESHEET)

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(COLORS["bg_primary"]))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(COLORS["text_primary"]))
    pal.setColor(QPalette.ColorRole.Base,            QColor(COLORS["bg_secondary"]))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor(COLORS["bg_card"]))
    pal.setColor(QPalette.ColorRole.Text,            QColor(COLORS["text_primary"]))
    pal.setColor(QPalette.ColorRole.Button,          QColor(COLORS["bg_hover"]))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(COLORS["text_primary"]))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(COLORS["accent"]))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(COLORS["text_muted"]))
    pal.setColor(QPalette.ColorRole.ToolTipBase,     QColor(COLORS["bg_card"]))
    pal.setColor(QPalette.ColorRole.ToolTipText,     QColor(COLORS["text_primary"]))
    app.setPalette(pal)
