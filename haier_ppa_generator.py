import sys
import os
import re
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QFileDialog, QTextEdit, 
                             QMessageBox, QGroupBox, QFormLayout, QSplitter, QScrollArea)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
import logging

# --- Настройка логирования ---
# Создаем логгер
logger = logging.getLogger("PPA_Generator")
logger.setLevel(logging.DEBUG) # DEBUG позволит записывать весь сырой текст из PDF

# Формат сообщений: Дата Время - Уровень - Сообщение
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# Обработчик для записи в файл (с поддержкой кириллицы)
file_handler = logging.FileHandler("ppa_generator.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

# Обработчик для вывода в консоль
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO) # В консоль выводим только основную информацию
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)
# -----------------------------


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
        logger.info(f"Начало обработки файла: {self.pdf_path}")
        try:
            result = self.extract_data(self.pdf_path)
            logger.info("Обработка PDF успешно завершена.")
            self.finished.emit(result)
        except Exception as e:
            logger.error(f"Критическая ошибка при обработке PDF: {str(e)}", exc_info=True)
            self.error.emit(str(e))

    def extract_data(self, path):
        text_content = ""
        
        # Попытка извлечь текст напрямую (улучшенные параметры tolerance)
        logger.info("Попытка прямого извлечения текста (pdfplumber)...")
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text(x_tolerance=2, y_tolerance=3)
                if text:
                    text_content += text + "\n"
        
        # Если текста мало (вероятно, это скан или векторный чертеж)
        if len(text_content.strip()) < 100:
            logger.warning("Текст не найден или его мало (скан/вектор). Запуск Tesseract OCR...")
            try:
                # Устанавливаем dpi=300 для высокого качества распознавания
                images = convert_from_path(path, dpi=300)
                ocr_text = ""
                for i, img in enumerate(images):
                    logger.info(f"OCR: обработка страницы {i+1} из {len(images)}...")
                    ocr_page = pytesseract.image_to_string(img, lang='rus+eng+chi_sim')
                    ocr_text += ocr_page + "\n"
                text_content = ocr_text
                logger.info("OCR распознавание завершено.")
            except Exception as ocr_err:
                logger.error(f"Ошибка Tesseract OCR: {ocr_err}")
        
        # --- ЛОГИРОВАНИЕ СЫРОГО ТЕКСТА ---
        logger.debug("--- ИЗВЛЕЧЕННЫЙ СЫРОЙ ТЕКСТ НАЧАЛО ---")
        logger.debug(f"\n{text_content}")
        logger.debug("--- ИЗВЛЕЧЕННЫЙ СЫРОЙ ТЕКСТ КОНЕЦ ---")
        # ---------------------------------
        
        material = self.find_material(text_content)
        tech_req = self.find_tech_requirements(text_content)
        
        logger.info(f"Найденный материал: '{material}'")
        logger.info(f"Найдено технических требований: {len(tech_req)} пунктов")

        data = {
            "material": material,
            "tech_req": tech_req,
            "raw_text": text_content
        }
        return data

        def find_material(self, text):
        """Улучшенный поиск материала в тексте чертежа (Title Block)"""
        # Убираем пустые строки для удобной работы с соседними строками
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # 1. Поиск по явным маркерам (с учетом двоеточий, тире или больших пробелов)
        # Добавлены русские сокращения "Мат-л", "Мат.", английское "MAT."
        marker_pattern = r'(?:Материал|Мат-л|Мат\.?|Material|Matl\.?|Mat\.?|材质)\s*(?:[:：\-]| {2,})\s*(.*)'
        
        for i, line in enumerate(lines):
            match = re.search(marker_pattern, line, re.IGNORECASE)
            if match:
                mat = match.group(1).strip()
                
                # Если после слова "Материал:" ничего нет, значение могло перенестись на следующую строку (в ячейку ниже)
                if not mat and i + 1 < len(lines):
                    next_line = lines[i+1]
                    # Проверяем, что следующая строка не является другим заголовком штампа (Вес, Масштаб и т.д.)
                    if len(next_line) < 50 and not re.search(r'(?:Weight|Mass|Scale|Масса|Масштаб|Вес)', next_line, re.IGNORECASE):
                        mat = next_line.strip()
                
                # Очистка от мусора (если справа прилип другой текст из соседней колонки штампа через много пробелов)
                mat = re.split(r' {2,}|\t', mat)[0].strip()
                
                # Ограничение длины защищает от случайного захвата целого абзаца
                if mat and len(mat) < 60:  
                    # Убираем возможные точки или лишние знаки на самом конце
                    return mat.rstrip(';.,')

        # 2. Умный поиск по словарю (если маркеры не сработали, а материал написан просто текстом)
        
        # Строгие аббревиатуры (ищутся с \b - граница слова, чтобы не найти "PC" внутри слова "PCS" или номера детали)
        exact_acronyms = [r'\bABS\b', r'\bPP\b', r'\bPC\b', r'\bPVC\b', r'\bPOM\b', r'\bPE\b', r'\bPET\b']
        
        # Расширенный словарь обычных материалов
        known_materials = [
            "Concrete", "Бетон", "混凝土", 
            "Plastic", "Пластик", "Пластмасса",
            "Stainless Steel", "Нержавеющая сталь", "Нержавейка",
            "Steel", "Сталь",
            "Aluminum", "Aluminium", "Алюминий", "Алюм.",
            "Brass", "Латунь", "Copper", "Медь", "Bronze", "Бронза",
            "Cast Iron", "Чугун", "Rubber", "Резина"
        ]
        
        # Сначала ищем аббревиатуры пластиков (только точное совпадение слова)
        for acronym in exact_acronyms:
            if re.search(acronym, text): # Здесь регистр важен, ищем именно заглавные
                return acronym.replace(r'\b', '') # Возвращаем без спецсимволов \b
                
        # Затем ищем обычные материалы (нечувствительно к регистру)
        lower_text = text.lower()
        for mat in known_materials:
            if mat.lower() in lower_text:
                return mat
                
        return ""


        def find_tech_requirements(self, text):
        """Извлечение технических требований с продвинутым поиском заголовка и улучшенными списками"""
        requirements = []
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        start_index = -1
        
        # 1. Регулярные выражения для поиска заголовков
        header_patterns = [
            r'^\s*(\d+[\.\)\、])?\s*(технические\s*требования|общие\s*указания|примечани[яе]|требования|спецификация|особые\s*отметки)',
            r'^\s*(\d+[\.\)\、])?\s*(technical\s*requirements|general\s*notes|notes|requirements|specifications)',
            r'^\s*(\d+[\.\)\、])?\s*(技术要求|注\s*意)'
        ]
        
        # 2. Сжатые ключевые слова для поиска "разреженного" текста
        compressed_keywords = [
            "техническиетребования", "notes", "technicalrequirements", 
            "примечания", "技术要求", "общиеуказания", "generalnotes",
            "спецификация", "особыеотметки", "requirements", "specifications"
        ]
        
        # УЛУЧШЕННЫЙ ПАТТЕРН ДЛЯ СПИСКОВ
        # Ловит: "1.", "1 )", "l.", "I.", "1-", "1:", "* ", "• ", "a)"
        list_pattern = r'^\s*(?:(?:\d+|[lI\|])\s*[\.\)\、\-\:]|[\*\-•·]\s+|[a-zA-Zа-яА-Я]\s*[\.\)]\s+)'
        
        # Поиск заголовка блока
        for i, line in enumerate(lines):
            lower_line = line.lower()
            compressed_line = re.sub(r'\s+', '', lower_line)
            
            match_regex = any(re.search(pat, lower_line) for pat in header_patterns)
            match_compressed = any(kw in compressed_line for kw in compressed_keywords) and len(compressed_line) < 30
            
            if match_regex or match_compressed:
                start_index = i
                break
        
        # Если заголовок найден, собираем пункты
        if start_index != -1:
            current_req = ""
            for i in range(start_index + 1, len(lines)):
                line = lines[i]
                
                # Признак конца блока (капс, без цифр, короткий)
                if line.isupper() and len(line) < 30 and not re.match(r'^\d', line) and len(line) > 3:
                    break
                
                # ИСПОЛЬЗУЕМ НОВЫЙ ПАТТЕРН ЗДЕСЬ
                if re.match(list_pattern, line):
                    if current_req:
                        requirements.append(current_req.strip())
                    current_req = line
                elif current_req:
                    current_req += " " + line
            
            if current_req:
                requirements.append(current_req.strip())
                
        # Fallback: Если заголовок не найден
        if not requirements:
            current_req = ""
            for line in lines:
                # ИСПОЛЬЗУЕМ НОВЫЙ ПАТТЕРН ЗДЕСЬ
                if re.match(list_pattern, line):
                    if current_req:
                        requirements.append(current_req.strip())
                    current_req = line
                elif current_req and not line.isupper() and len(line) > 2:
                    current_req += " " + line
                else:
                    if current_req:
                        requirements.append(current_req.strip())
                        current_req = ""
            if current_req:
                requirements.append(current_req.strip())
        
        # Очищаем результат от случайного мусора (слишком короткие строки)
        return [req for req in requirements if len(req) > 5]


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
            # Отображаем требования в виде текста для предпросмотра (каждый пункт с новой строки)
            self.edt_tech_req.setText("\n".join(data['tech_req']))
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
            
            # Получаем текст требований и разбиваем на пункты
            tech_req_text = self.edt_tech_req.toPlainText()
            # Разбиваем по строкам, убираем пустые
            tech_req_list = [line.strip() for line in tech_req_text.split('\n') if line.strip()]
            
            # Данные для замены (базовые)
            replacements = {
                "{SUPPLIER}": self.in_supplier.text(),
                "{PART_NAME}": self.in_part_name.text(),
                "{PART_NUMBER}": self.in_part_number.text(),
                "{MATERIAL}": self.in_material.text(),
            }
            
            # Добавляем первые 5 требований в replacements
            for i in range(5):
                key = f"{{TECH_REQ_{i+1}}}"
                if i < len(tech_req_list):
                    replacements[key] = tech_req_list[i]
                else:
                    replacements[key] = ""  # Если требований меньше, чем ячеек, оставляем пустым
            
            # Также поддерживаем старый ключ {TECH_REQ} для совместимости (все требования вместе)
            replacements["{TECH_REQ}"] = tech_req_text
            
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
                        
                        # Особая обработка для длинного текста требований (если используется общий ключ)
                        if "{TECH_REQ}" in original and "{TECH_REQ_" not in original:
                            # Включаем перенос по словам
                            cell.alignment = cell.alignment.copy(wrap_text=True)
                        
                        if modified != original:
                            cell.value = modified
            
            wb.save(save_path)
            self.status_bar.showMessage(f"Файл успешно сохранен: {save_path}")
            QMessageBox.information(self, "Успех", f"Файл успешно создан!\n{save_path}")
            
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
