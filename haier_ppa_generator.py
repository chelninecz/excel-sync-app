import sys
import os
import re
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QFileDialog, QTextEdit, 
                             QMessageBox, QGroupBox, QFormLayout, QSplitter, QScrollArea)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

# Библиотеки для работы с PDF и Excel
try:
    import pdfplumber
    import pytesseract
    from pdf2image import convert_from_path
    import openpyxl
except ImportError as e:
    print(f"Ошибка импорта библиотек: {e}")
    print("Убедитесь, что установлены: pip install pdfplumber pytesseract pdf2image openpyxl pillow")
    print("Также необходим установленный Tesseract-OCR в системе.")
    sys.exit(1)

# Настройка пути к Tesseract (для Windows часто требуется указать явно)
# Если у вас Tesseract установлен в стандартную папку, эта строка может не понадобиться,
# но лучше раскомментировать и проверить путь, если возникнут ошибки OCR.
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class PDFProcessor(QThread):
    """Поток для обработки PDF, чтобы не замораживать интерфейс"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, pdf_path):
        super().__init__()
        self.pdf_path = pdf_path

    def run(self):
        try:
            result = self.extract_data(self.pdf_path)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

    def extract_data(self, path):
        text_content = ""
        
        # Попытка извлечь текст напрямую
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_content += text + "\n"
        
        # Если текста мало, возможно это скан -> используем OCR
        # Порог "мало текста" условный, например, меньше 50 символов на страницу
        if len(text_content.strip()) < 50:
            print("Текст не найден или его мало. Запуск OCR...")
            try:
                images = convert_from_path(path)
                ocr_text = ""
                for img in images:
                    # lang='rus+eng+chi_sim' требует установки этих пакетов языков в Tesseract
                    ocr_page = pytesseract.image_to_string(img, lang='rus+eng+chi_sim')
                    ocr_text += ocr_page + "\n"
                text_content = ocr_text
            except Exception as ocr_err:
                print(f"OCR не удался: {ocr_err}")
                # Если OCR упал, возвращаем то, что есть
        
        data = {
            "material": self.find_material(text_content),
            "tech_req": self.find_tech_requirements(text_content),
            "raw_text": text_content # Для отладки
        }
        return data

    def find_material(self, text):
        """Поиск материала в тексте"""
        lines = text.split('\n')
        patterns = [
            r'(?:Материал|Material|材质)\s*[:：]\s*(.+?)(?:[;,.]|$)',
            r'(?:Concrete|Бетон|混凝土|Пластик|Plastic|Сталь|Steel)\s*',
        ]
        
        # Ищем по ключевым словам в контексте
        for line in lines:
            # Приоритет русскому и китайскому/английскому
            if re.search(r'Материал\s*[:：]', line) or re.search(r'Material\s*[:：]', line) or re.search(r'材质', line):
                # Очищаем строку от ключевых слов
                mat = re.sub(r'.*?(?:Материал|Material|材质)\s*[:：]\s*', '', line)
                mat = mat.split(';')[0].split('.')[0].strip()
                if mat:
                    return mat
        
        # Если явного маркера нет, ищем известные материалы во всем тексте
        known_materials = ["Concrete", "Бетон", "混凝土", "Plastic", "Пластик", "Steel", "Сталь", "Алюминий", "Aluminum"]
        for mat in known_materials:
            if mat in text:
                return mat
                
        return ""

    def find_tech_requirements(self, text):
        """Извлечение технических требований"""
        requirements = []
        lines = text.split('\n')
        
        in_block = False
        block_keywords = ["технические требования", "notes", "技术要求", "technical requirements"]
        
        # Простой эвристический алгоритм: ищем нумерованный список после ключевых слов
        # Или просто собираем строки, начинающиеся с цифры и точки/запятой
        
        # Попытка найти блок
        start_index = -1
        for i, line in enumerate(lines):
            lower_line = line.lower()
            if any(kw in lower_line for kw in block_keywords):
                start_index = i
                break
        
        if start_index != -1:
            # Собираем строки после заголовка
            for i in range(start_index + 1, len(lines)):
                line = lines[i].strip()
                if not line:
                    continue
                # Если нашли конец блока (например, подпись или новый большой заголовок)
                if len(line) < 5 and not line[0].isdigit():
                    break
                
                # Фильтруем: оставляем строки, похожие на пункты требований
                # Обычно они начинаются с цифры или содержат ключевые слова качества
                if re.match(r'^\d+[.,、]', line) or any(w in line for w in ['должен', 'must', 'should', 'check', 'проверк', 'размер', 'size', 'mm', 'cm']):
                    # Убираем дублирование языка, если нужно (упрощенно берем всё подряд)
                    # В реальном проекте тут нужна сложная логика выбора языка
                    requirements.append(line)
        
        # Если список пуст, попробуем найти любые нумерованные списки в тексте
        if not requirements:
            for line in lines:
                line = line.strip()
                if re.match(r'^\d+[.,、]', line):
                    requirements.append(line)
        
        return "\n".join(requirements)

class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.pdf_path = ""
        self.template_path = ""
        self.processor = None
        
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Haier PPA Generator")
        self.setGeometry(100, 100, 900, 700)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # --- Верхняя часть: Выбор файлов ---
        file_group = QGroupBox("1. Выбор файлов")
        file_layout = QFormLayout()
        
        self.btn_pdf = QPushButton("Выбрать PDF чертеж")
        self.btn_pdf.clicked.connect(self.select_pdf)
        self.lbl_pdf = QLabel("Файл не выбран")
        
        self.btn_template = QPushButton("Выбрать Excel шаблон")
        self.btn_template.clicked.connect(self.select_template)
        self.lbl_template = QLabel("Файл не выбран")
        
        file_layout.addRow(self.btn_pdf, self.lbl_pdf)
        file_layout.addRow(self.btn_template, self.lbl_template)
        file_group.setLayout(file_layout)
        
        # --- Средняя часть: Ввод данных и Предпросмотр ---
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Форма ввода
        input_group = QGroupBox("2. Данные детали")
        input_layout = QFormLayout()
        
        self.in_supplier = QLineEdit()
        self.in_part_name = QLineEdit()
        self.in_part_number = QLineEdit()
        
        # Поля, которые заполняются автоматически, но можно править
        self.in_material = QLineEdit()
        self.in_material.setPlaceholderText("Будет извлечено из PDF...")
        
        self.edt_tech_req = QTextEdit()
        self.edt_tech_req.setMaximumHeight(150)
        self.edt_tech_req.setPlaceholderText("Технические требования будут извлечены здесь...")
        
        input_layout.addRow("Поставщик (Supplier):", self.in_supplier)
        input_layout.addRow("Название детали (Part Name):", self.in_part_name)
        input_layout.addRow("Номер детали (Part Number):", self.in_part_number)
        input_layout.addRow("Материал (Material):", self.in_material)
        input_layout.addRow("Требования (Notes):", self.edt_tech_req)
        
        input_group.setLayout(input_layout)
        
        # Кнопка обработки
        self.btn_process = QPushButton("Анализировать PDF")
        self.btn_process.clicked.connect(self.start_processing)
        input_layout.addRow(self.btn_process)
        
        splitter.addWidget(input_group)
        
        # Инструкция
        info_label = QLabel("3. Нажмите 'Сгенерировать Excel', когда данные проверены.")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        splitter.addWidget(info_label)
        
        main_layout.addWidget(file_group)
        main_layout.addWidget(splitter)
        
        # --- Нижняя часть: Действия ---
        action_layout = QHBoxLayout()
        action_layout.addStretch()
        
        self.btn_generate = QPushButton("Сгенерировать Excel")
        self.btn_generate.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px; font-weight: bold;")
        self.btn_generate.clicked.connect(self.generate_excel)
        self.btn_generate.setEnabled(False) # Активна только после анализа
        
        action_layout.addWidget(self.btn_generate)
        main_layout.addLayout(action_layout)
        
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Готов к работе")

    def select_pdf(self):
        file, _ = QFileDialog.getOpenFileName(self, "Выберите PDF чертеж", "", "PDF Files (*.pdf)")
        if file:
            self.pdf_path = file
            self.lbl_pdf.setText(os.path.basename(file))
            self.status_bar.showMessage(f"PDF выбран: {file}")

    def select_template(self):
        file, _ = QFileDialog.getOpenFileName(self, "Выберите Excel шаблон", "", "Excel Files (*.xlsx)")
        if file:
            self.template_path = file
            self.lbl_template.setText(os.path.basename(file))
            self.status_bar.showMessage(f"Шаблон выбран: {file}")

    def start_processing(self):
        if not self.pdf_path:
            QMessageBox.warning(self, "Ошибка", "Сначала выберите PDF файл!")
            return
        
        self.btn_process.setEnabled(False)
        self.btn_process.setText("Обработка...")
        self.status_bar.showMessage("Идет анализ PDF и распознавание текста...")
        
        self.processor = PDFProcessor(self.pdf_path)
        self.processor.finished.connect(self.on_processing_finished)
        self.processor.error.connect(self.on_processing_error)
        self.processor.start()

    def on_processing_finished(self, data):
        self.btn_process.setEnabled(True)
        self.btn_process.setText("Анализировать PDF")
        self.status_bar.showMessage("Анализ завершен")
        
        # Заполняем поля
        if data['material']:
            self.in_material.setText(data['material'])
        
        if data['tech_req']:
            self.edt_tech_req.setText(data['tech_req'])
        else:
            self.edt_tech_req.setText("Требования не найдены автоматически. Пожалуйста, введите их вручную.")
            
        self.btn_generate.setEnabled(True)
        
        if not data['material'] or not data['tech_req']:
            QMessageBox.information(self, "Внимание", "Некоторые данные не удалось распознать автоматически. Пожалуйста, проверьте поля и дополните их вручную.")

    def on_processing_error(self, msg):
        self.btn_process.setEnabled(True)
        self.btn_process.setText("Анализировать PDF")
        self.status_bar.showMessage("Ошибка при обработке")
        QMessageBox.critical(self, "Ошибка", f"Произошла ошибка при чтении PDF:\n{msg}")

    def generate_excel(self):
        if not self.template_path:
            QMessageBox.warning(self, "Ошибка", "Выберите шаблон Excel!")
            return
        
        save_path, _ = QFileDialog.getSaveFileName(self, "Сохранить результат", "", "Excel Files (*.xlsx)")
        if not save_path:
            return
            
        try:
            self.status_bar.showMessage("Генерация файла...")
            
            # Загружаем шаблон
            wb = openpyxl.load_workbook(self.template_path)
            ws = wb.active # Берем первый лист
            
            # Данные для замены
            replacements = {
                "{SUPPLIER}": self.in_supplier.text(),
                "{PART_NAME}": self.in_part_name.text(),
                "{PART_NUMBER}": self.in_part_number.text(),
                "{MATERIAL}": self.in_material.text(),
                "{TECH_REQ}": self.edt_tech_req.toPlainText()
            }
            
            # Проход по всем ячейкам
            for row in ws.iter_rows():
                for cell in row:
                    if cell.value and isinstance(cell.value, str):
                        original = cell.value
                        modified = original
                        
                        # Замена ключевых слов
                        for key, val in replacements.items():
                            if key in modified:
                                modified = modified.replace(key, val)
                        
                        # Особая обработка для длинного текста требований
                        if key == "{TECH_REQ}" and key in original:
                            # Включаем перенос по словам
                            cell.alignment = cell.alignment.copy(wrap_text=True)
                            # Можно принудительно задать высоту строки, если нужно
                            # ws.row_dimensions[cell.row].height = 100 
                        
                        if modified != original:
                            cell.value = modified
            
            wb.save(save_path)
            self.status_bar.showMessage(f"Файл успешно сохранен: {save_path}")
            QMessageBox.success(self, "Успех", f"Файл успешно создан!\n{save_path}")
            
        except Exception as e:
            self.status_bar.showMessage("Ошибка сохранения")
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать файл:\n{str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Установка стиля для приятного вида
    app.setStyle("Fusion")
    window = App()
    window.show()
    sys.exit(app.exec())
