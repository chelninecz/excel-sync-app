import sys
import os
import re
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QFileDialog, QTextEdit, 
                             QMessageBox, QGroupBox, QFormLayout, QSplitter)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
import logging

# --- Настройка логирования ---
logger = logging.getLogger("PPA_Generator")
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

file_handler = logging.FileHandler("ppa_generator.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)
# -----------------------------

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
        
        logger.info("Попытка прямого извлечения текста (pdfplumber)...")
        try:
            with pdfplumber.open(path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text(x_tolerance=2, y_tolerance=3)
                    if text:
                        text_content += text + "\n"
        except Exception as e:
            logger.error(f"Ошибка pdfplumber: {e}")
        
        # Предварительная проверка найденных данных
        material = self.find_material(text_content)
        tech_req = self.find_tech_requirements(text_content)
        
        # ГЛАВНОЕ ИСПРАВЛЕНИЕ: Если pdfplumber не нашел требования (текст в кривых) 
        # или текста слишком мало (< 300 символов), принудительно запускаем OCR!
        if len(text_content.strip()) < 300 or not tech_req:
            logger.warning("Требования не найдены напрямую (возможно текст в кривых). Запуск Tesseract OCR...")
            try:
                # --- АВТОМАТИЧЕСКИЙ ПОИСК POPPLER РЯДОМ СО СКРИПТОМ ---
                # Получаем абсолютный путь к папке, где лежит наш скрипт (или .exe, если скомпилируем)
                if getattr(sys, 'frozen', False):
                    # Если программа скомпилирована через PyInstaller
                    base_path = sys._MEIPASS
                else:
                    # Если запускаем как обычный .py скрипт
                    base_path = os.path.dirname(os.path.abspath(__file__))
                
                # Формируем путь к папке bin внутри poppler
                # Ожидается структура: папка_со_скриптом/poppler/Library/bin
                poppler_path = os.path.join(base_path, 'poppler', 'Library', 'bin')
                
                # Проверяем, действительно ли poppler там лежит (чтобы вывести понятную ошибку, если папки нет)
                if not os.path.exists(poppler_path):
                     logger.error(f"Не найдена папка poppler по пути: {poppler_path}. Пожалуйста, положите папку poppler рядом со скриптом.")
                     raise FileNotFoundError(f"Poppler не найден в {poppler_path}")

                logger.info(f"Используем poppler из: {poppler_path}")
                images = convert_from_path(path, dpi=400, poppler_path=poppler_path)
              
                # --- АВТОМАТИЧЕСКИЙ ПОИСК TESSERACT РЯДОМ СО СКРИПТОМ ---
                tesseract_path = os.path.join(base_path, 'Tesseract-OCR', 'tesseract.exe')
                
                if not os.path.exists(tesseract_path):
                    logger.error(f"Не найден Tesseract по пути: {tesseract_path}. Пожалуйста, положите папку Tesseract-OCR рядом со скриптом.")
                    raise FileNotFoundError(f"Tesseract не найден в {tesseract_path}")
                
                # Указываем библиотеке точный путь к exe-файлу
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
                logger.info(f"Используем tesseract из: {tesseract_path}")
                # ---------------------------------------------------------
                
                ocr_text = ""
                for i, img in enumerate(images):
                    logger.info(f"OCR: обработка страницы {i+1} из {len(images)}...")
                    ocr_page = pytesseract.image_to_string(img, lang='rus+eng+chi_sim')
                    ocr_text += ocr_page + "\n"
                
                # Добавляем распознанный текст к общему
                text_content = text_content + "\n\n" + ocr_text
                logger.info("OCR распознавание завершено.")
                
                # Повторный поиск в распознанном OCR тексте
                material = self.find_material(text_content) or material
                tech_req = self.find_tech_requirements(text_content)
                
            except Exception as ocr_err:
                logger.error(f"Ошибка Tesseract OCR: {ocr_err}")
        
        logger.debug("--- ИЗВЛЕЧЕННЫЙ СЫРОЙ ТЕКСТ НАЧАЛО ---")
        logger.debug(f"\n{text_content}")
        logger.debug("--- ИЗВЛЕЧЕННЫЙ СЫРОЙ ТЕКСТ КОНЕЦ ---")
        
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
        lines = [line.strip() for line in text.split('\n') if line.strip()]
      
        # Добавлено слово "材料" для китайских чертежей
        # Обновленный поиск материала
        marker_pattern = r'(?:Материал|Мат-л|Мат\.?|Material|Matl\.?|Mat\.?|材质|材料)\s*(?:[:：\-]| {2,})\s*(.*)'
        
        for i, line in enumerate(lines):
            match = re.search(marker_pattern, line, re.IGNORECASE)
            if match:
                mat = match.group(1).strip()
                
                if not mat and i + 1 < len(lines):
                    next_line = lines[i+1]
                    if len(next_line) < 50 and not re.search(r'(?:Weight|Mass|Scale|Масса|Масштаб|Вес)', next_line, re.IGNORECASE):
                        mat = next_line.strip()
                
                mat = re.split(r' {2,}|\t', mat)[0].strip()
                
                # ИЗМЕНЕНИЕ: Добавлена защита от китайского названия компании
                mat_upper = mat.upper()
                if not mat or "HAIER" in mat_upper or "COMPANY" in mat_upper or "INDUSTR" in mat_upper or "海尔" in mat or "产业" in mat:
                    continue 
                
                if mat and len(mat) < 60:  
                    return mat.rstrip(';.,')
        
        for i, line in enumerate(lines):
            match = re.search(marker_pattern, line, re.IGNORECASE)
            if match:
                mat = match.group(1).strip()
                
                if not mat and i + 1 < len(lines):
                    next_line = lines[i+1]
                    if len(next_line) < 50 and not re.search(r'(?:Weight|Mass|Scale|Масса|Масштаб|Вес)', next_line, re.IGNORECASE):
                        mat = next_line.strip()
                
                mat = re.split(r' {2,}|\t', mat)[0].strip()
                
                if mat and len(mat) < 60:  
                    return mat.rstrip(';.,')

        exact_acronyms = [r'\bABS\b', r'\bPP\b', r'\bPC\b', r'\bPVC\b', r'\bPOM\b', r'\bPE\b', r'\bPET\b']
        
        known_materials = [
            "Concrete", "Бетон", "混凝土", 
            "Plastic", "Пластик", "Пластмасса",
            "Stainless Steel", "Нержавеющая сталь", "Нержавейка",
            "Steel", "Сталь",
            "Aluminum", "Aluminium", "Алюминий", "Алюм.",
            "Brass", "Латунь", "Copper", "Медь", "Bronze", "Бронза",
            "Cast Iron", "Чугун", "Rubber", "Резина"
        ]
        
        for acronym in exact_acronyms:
            if re.search(acronym, text): 
                return acronym.replace(r'\b', '') 
                
        lower_text = text.lower()
        for mat in known_materials:
            if mat.lower() in lower_text:
                return mat
                
        return ""

    def find_tech_requirements(self, text):
    def find_tech_requirements(self, text):
        """Извлечение требований с отсечением штампа чертежа"""
        requirements = []
        
        # --- 1. ОЧИСТКА ТЕКСТА ---
        text = re.sub(r'([一-龥])\s+([一-龥])', r'\1\2', text)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        cleaned_lines = []
        
        # Разделители: отсекаем всё, что правее этих слов (так как штамп находится справа от требований)
        noise_splitters = [
            r'\bDWG\s*No', r'审核\s*REVIEW', r'设计\s*DESIGN', r'会签\s*CHECK',
            r'批准\s*APPROVE', r'日期\s*DATE', r'标记\s*MARK', r'单位\s*DIMENSION',
            r'质量\s*WEIGHT', r'比例\s*SCALE', r'共\s*\d+\s*张', r'第\s*\d+\s*张',
            r'材料\s*MATERIAL', r'\bTITLE:', r'处数\s*QTY', r'更改文件号', 
            r'签名\s*AUTHOR', r'海尔洗衣机', r'俄罗斯洗衣机', r'ENERGYCONSUMPTIONSTICKER'
        ]
        
        for line in lines:
            cl = line
            # Если в строке есть слово из штампа, отсекаем всё, что после него (включая само слово)
            for splitter in noise_splitters:
                cl = re.split(splitter, cl, flags=re.IGNORECASE)[0]
            
            cl = cl.strip()
            # Пропускаем мусор
            if len(cl) > 2 and not re.match(r'^\d+\)\s*©.*', cl):
                cleaned_lines.append(cl)
                
        lines = cleaned_lines
        # ------------------------
        
        start_index = -1
        # ... (ДАЛЬШЕ ИДЕТ ВАШ СТАРЫЙ КОД МЕТОДА БЕЗ ИЗМЕНЕНИЙ, начиная со start_index = -1) ...
        
        header_patterns = [
            r'^\s*(\d+[\.\)\、])?\s*(технические\s*требования|общие\s*указания|примечани[яе]|требования|спецификация|особые\s*отметки)',
            r'^\s*(\d+[\.\)\、])?\s*(technical\s*requirements|general\s*notes|notes|requirements|specifications)',
            r'^\s*(\d+[\.\)\、])?\s*(技术要求|注\s*意)'
        ]
        
        compressed_keywords = [
            "техническиетребования", "notes", "technicalrequirements", 
            "примечания", "技术要求", "общиеуказания", "generalnotes",
            "спецификация", "особыеотметки", "requirements", "specifications"
        ]
        
        # Добавлен допуск на треугольники (△, A) перед номером, которые часто ставят инженеры
        list_pattern = r'^\s*(?:[△∆▲A-Z]\s*)?(?:\d+|[lI\|])\s*[\.\)\、\-\:]'
        
        for i, line in enumerate(lines):
            lower_line = line.lower()
            compressed_line = re.sub(r'\s+', '', lower_line)
            
            match_regex = any(re.search(pat, lower_line) for pat in header_patterns)
            match_compressed = any(kw in compressed_line for kw in compressed_keywords) and len(compressed_line) < 30
            
            if match_regex or match_compressed:
                start_index = i
                break
        
        if start_index != -1:
            current_req = ""
            current_num = None
            for i in range(start_index + 1, len(lines)):
                line = lines[i]
                
                if line.isupper() and len(line) < 30 and not re.match(r'^\d', line) and len(line) > 3:
                    break
                
                match = re.match(list_pattern, line)
                if match:
                    num_match = re.search(r'\d+', match.group())
                    num = num_match.group() if num_match else None
                    
                    if current_req:
                        if num and current_num == num:
                            current_req += "\n" + line
                            continue
                        else:
                            requirements.append(current_req.strip())
                    current_req = line
                    current_num = num
                elif current_req:
                    current_req += " " + line
            
            if current_req:
                requirements.append(current_req.strip())
                
        if not requirements:
            current_req = ""
            current_num = None
            for line in lines:
                match = re.match(list_pattern, line)
                if match:
                    num_match = re.search(r'\d+', match.group())
                    num = num_match.group() if num_match else None
                    
                    if current_req:
                        if num and current_num == num:
                            current_req += "\n" + line
                            continue
                        else:
                            requirements.append(current_req.strip())
                    current_req = line
                    current_num = num
                elif current_req and not line.isupper() and len(line) > 2:
                    current_req += " " + line
                else:
                    if current_req:
                        requirements.append(current_req.strip())
                        current_req = ""
            if current_req:
                requirements.append(current_req.strip())
        
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
        
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        input_group = QGroupBox("2. Данные детали")
        input_layout = QFormLayout()
        
        self.in_supplier = QLineEdit()
        self.in_part_name = QLineEdit()
        self.in_part_number = QLineEdit()
        
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
        
        self.btn_process = QPushButton("Анализировать PDF")
        self.btn_process.clicked.connect(self.start_processing)
        input_layout.addRow(self.btn_process)
        
        splitter.addWidget(input_group)
        
        info_label = QLabel("3. Нажмите 'Сгенерировать Excel', когда данные проверены.")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        splitter.addWidget(info_label)
        
        main_layout.addWidget(file_group)
        main_layout.addWidget(splitter)
        
        action_layout = QHBoxLayout()
        action_layout.addStretch()
        
        self.btn_generate = QPushButton("Сгенерировать Excel")
        self.btn_generate.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px; font-weight: bold;")
        self.btn_generate.clicked.connect(self.generate_excel)
        self.btn_generate.setEnabled(False) 
        
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
        
        if data['material']:
            self.in_material.setText(data['material'])
        
        if data['tech_req']:
            # ВАЖНО: Разделяем пункты ПУСТОЙ СТРОКОЙ (\n\n), чтобы внутренние переводы строк не ломали логику
            self.edt_tech_req.setText("\n\n".join(data['tech_req']))
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
            
            wb = openpyxl.load_workbook(self.template_path)
            ws = wb.active 
            
            tech_req_text = self.edt_tech_req.toPlainText()
            
            # ВАЖНО: Разбиваем текст только по ПУСТЫМ строкам (сохраняя переводы внутри пункта)
            tech_req_list = [item.strip() for item in re.split(r'\n\s*\n', tech_req_text) if item.strip()]
            
            replacements = {
                "{SUPPLIER}": self.in_supplier.text(),
                "{PART_NAME}": self.in_part_name.text(),
                "{PART_NUMBER}": self.in_part_number.text(),
                "{MATERIAL}": self.in_material.text(),
            }
            
            # Теперь поддерживаем до 50 требований, а не 5!
            for i in range(50):
                key = f"{{TECH_REQ_{i+1}}}"
                if i < len(tech_req_list):
                    replacements[key] = tech_req_list[i]
                else:
                    replacements[key] = ""  
            
            replacements["{TECH_REQ}"] = tech_req_text
            
            for row in ws.iter_rows():
                for cell in row:
                    if cell.value and isinstance(cell.value, str):
                        original = str(cell.value)
                        
                        # Защита от опечаток: убираем лишние пробелы в Excel { TECH_REQ_1 } -> {TECH_REQ_1}
                        modified = re.sub(r'\{\s+([^}]+?)\s+\}', r'{\1}', original)
                        
                        for key, val in replacements.items():
                            if key in modified:
                                modified = modified.replace(key, val)
                        
                        if modified != original:
                            cell.value = modified
                            # Если текст длинный, автоматически включаем перенос по словам в ячейке
                            if "{" not in modified and len(modified) > 15:
                                cell.alignment = cell.alignment.copy(wrap_text=True)
            
            wb.save(save_path)
            self.status_bar.showMessage(f"Файл успешно сохранен: {save_path}")
            QMessageBox.information(self, "Успех", f"Файл успешно создан!\n{save_path}")
            
        except Exception as e:
            self.status_bar.showMessage("Ошибка сохранения")
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать файл:\n{str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = App()
    window.show()
    sys.exit(app.exec())
