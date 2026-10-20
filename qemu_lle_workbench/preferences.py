"""Global UI preferences; VM configuration remains in the project files."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QFormLayout, QSpinBox, QVBoxLayout)
from .i18n import settings, tr


def read_preferences():
    store = settings()
    def boolean(key, default):
        return str(store.value('ui/'+key, str(default))).lower() in {'true', '1'}
    def integer(key, default, minimum, maximum):
        try: return max(minimum, min(maximum, int(store.value('ui/'+key, default))))
        except (ValueError, TypeError): return default
    return {'simple': boolean('simple', False), 'theme': str(store.value('ui/theme', 'system')),
        'fontSize': integer('fontSize', 0, 0, 24),
        'logLines': integer('logLines', 10000, 100, 100000),
        'autoScroll': boolean('autoScroll', True)}


class PreferencesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr('Общие настройки'))
        values = read_preferences()
        layout = QVBoxLayout(self); form = QFormLayout(); layout.addLayout(form)
        self.simple = QCheckBox(tr('Лёгкий режим — скрыть расширенные вкладки'))
        self.simple.setChecked(values['simple']); form.addRow(self.simple)
        self.theme = QComboBox()
        for label,key in [('Системная', 'system'), ('Светлая', 'light'), ('Тёмная', 'dark')]:
            self.theme.addItem(tr(label),key)
        self.theme.setCurrentIndex(max(0,self.theme.findData(values['theme'])))
        form.addRow(tr('Тема'),self.theme)
        self.font = QSpinBox(); self.font.setRange(0,24); self.font.setSpecialValueText(tr('Системный размер'))
        self.font.setValue(values['fontSize']); form.addRow(tr('Размер шрифта'), self.font)
        self.lines = QSpinBox(); self.lines.setRange(100,100000); self.lines.setValue(values['logLines'])
        form.addRow(tr('Максимум строк консоли'),self.lines)
        self.scroll = QCheckBox(tr('Автопрокрутка консоли')); self.scroll.setChecked(values['autoScroll'])
        form.addRow(self.scroll)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def save(self):
        values = {'simple': self.simple.isChecked(), 'theme': self.theme.currentData(),
            'fontSize': self.font.value(), 'logLines': self.lines.value(), 'autoScroll': self.scroll.isChecked()}
        store = settings()
        for key,value in values.items(): store.setValue('ui/'+key,value)
        store.sync()


def apply_theme(app, theme, system_palette):
    if not hasattr(app, '_chilled_system_style'):
        app._chilled_system_style = app.style().objectName()
    if theme == 'system':
        app.setStyle(app._chilled_system_style)
        app.setPalette(system_palette); return
    app.setStyle('Fusion')
    palette = QPalette()
    dark = theme == 'dark'
    background, base, text = ('#252525','#191919','#eeeeee') if dark else ('#f2f2f2','#ffffff','#202020')
    for role,color in [(QPalette.Window,background),(QPalette.Base,base),(QPalette.AlternateBase,background),
        (QPalette.WindowText,text),(QPalette.Text,text),(QPalette.Button,background),(QPalette.ButtonText,text),
        (QPalette.ToolTipBase,base),(QPalette.ToolTipText,text),(QPalette.Highlight,'#287cce'),
        (QPalette.HighlightedText,'#ffffff'),(QPalette.Link,'#55aaff')]:
        palette.setColor(role,QColor(color))
    palette.setColor(QPalette.Disabled,QPalette.Text,QColor('#888888'))
    palette.setColor(QPalette.Disabled,QPalette.ButtonText,QColor('#888888'))
    app.setPalette(palette)
