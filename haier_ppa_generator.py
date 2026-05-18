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
    from pdf2image import convert_from_path
    import openpyxl
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR
except ImportError as e:
    print(f"Ошибка импорта библиотек: {e}")
    print("Убедитесь, что установлены: pip install pdfplumber pdf2image openpyxl pillow numpy rapidocr-onnxruntime PyQt6")
    sys.exit(1)


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
        
        material = self.find_material(text_content)
        tech_req = self.find_tech_requirements(text_content)
        
        if len(text_content.strip()) < 300 or not tech_req:
            logger.warning("Требования не найдены напрямую (возможно текст в кривых). Запуск RapidOCR...")
            try:
                if getattr(sys, 'frozen', False):
                    base_path = sys._MEIPASS
                else:
                    base_path = os.path.dirname(os.path.abspath(__file__))
                
                poppler_path = os.path.join(base_path, 'poppler', 'Library', 'bin')
                images = convert_from_path(path, dpi=400, poppler_path=poppler_path)
              
                logger.info("Инициализация движка RapidOCR с геометрической реконструкцией текста...")
                ocr_engine = RapidOCR()
                
                ocr_text = ""
                for i, img in enumerate(images):
                    logger.info(f"OCR: обработка страницы {i+1} из {len(images)}...")
                    img_np = np.array(img)
                    result, elapse = ocr_engine(img_np)
                    
                    if result:
                        # 1. Сортируем блоки по Y (сверху вниз)
                        sorted_by_y = sorted(result, key=lambda b: sum(pt[1] for pt in b[0]) / 4)
                        lines_blocks = []
                        current_line = []
                        
                        for box in sorted_by_y:
                            if not current_line:
                                current_line.append(box)
                                continue
                                
                            prev_box = current_line[-1]
                            y_prev = sum(pt[1] for pt in prev_box[0]) / 4
                            y_curr = sum(pt[1] for pt in box[0]) / 4
                            h_curr = box[0][3][1] - box[0][0][1]
                            
                            # Если разница по Y меньше половины высоты строки - это одна строка
                            if abs(y_curr - y_prev) < (h_curr * 0.6):
                                current_line.append(box)
                            else:
                                lines_blocks.append(current_line)
                                current_line = [box]
                                
                        if current_line:
                            lines_blocks.append(current_line)
                            
                        # 2. Склеиваем строки, соблюдая горизонтальные (X) отступы
                        page_text = ""
                        for line_boxes in lines_blocks:
                            # Сортируем блоки в строке по X (слева направо)
                            line_boxes.sort(key=lambda b: sum(pt[0] for pt in b[0]) / 4)
                            line_str = ""
                            last_x = 0
                            
                            for b in line_boxes:
                                x_min = min(pt[0] for pt in b[0])
                                text = b[1]
                                
                                if last_x == 0:
                                    line_str += text
                                else:
                                    gap = x_min - last_x
                                    h = b[0][3][1] - b[0][0][1]
                                    # Если расстояние между блоками большое (разные колонки), ставим большой разделитель
                                    if gap > h * 2:
                                        line_str += "    " + text
                                    else:
                                        line_str += " " + text
                                last_x = max(pt[0] for pt in b[0])
                                
                            page_text += line_str + "\n"
                            
                        ocr_text += page_text + "\n"
                
                text_content = text_content + "\n\n" + ocr_text
                logger.info("RapidOCR распознавание завершено.")
                
                material = self.find_material(text_content) or material
                tech_req = self.find_tech_requirements(text_content)
                
            except Exception as ocr_err:
                logger.error(f"Ошибка RapidOCR: {ocr_err}")
        
        logger.info(f"Найденный материал: '{material}'")
        logger.info(f"Найдено технических требований: {len(tech_req)} пунктов")
        
        return {
            "material": material,
            "tech_req": tech_req,
            "raw_text": text_content
        }

    def find_material(self, text):
        """Улучшенный поиск материала в тексте чертежа (Title Block)"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
      
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
        requirements = []
        
        # 1. Убираем лишние пробелы между китайскими символами
        text = re.sub(r'([一 - 龥])\s+([一 - 龥])', r'\1\2', text)
        
        # 2. Разделяем китайские и латинские символы/цифры
        text = re.sub(r'([一 - 龥])([A-Za-z0-9])', r'\1 \2', text)
        text = re.sub(r'([A-Za-z0-9])([一 - 龥])', r'\1 \2', text)
        
        # 3. [a-z][A-Z] для camelCase
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
        
        # 4. Разделяем вокруг знаков препинания
        for char in '<>()[]{};:,.':
            text = re.sub(r'([a-zA-Z])(' + re.escape(char) + ')', r'\1 \2', text)
            text = re.sub('(' + re.escape(char) + r')([a-zA-Z])', r'\1 \2', text)
        
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        noise_splitters = [
            r'\bDWG\s*No', r'审核\s*REVIEW', r'设计\s*DESIGN', r'会签\s*CHECK',
            r'批准\s*APPROVE', r'日期\s*DATE', r'标记\s*MARK', r'单位\s*DIMENSION',
            r'质量\s*WEIGHT', r'比例\s*SCALE', r'共\s*\d+\s*张', r'第\s*\d+\s*张',
            r'材料\s*MATERIAL', r'\bTITLE:', r'处数\s*QTY', r'更改文件号', 
            r'签名\s*AUTHOR', r'海尔洗衣机', r'俄罗斯洗衣机', r'ENERGYCONSUMPTIONSTICKER'
        ]
        
        for line in lines:
            cl = line
            # Очистка левого вертикального штампа чертежа
            cl = re.sub(r'(旧底图总号|底图总号|签\s*字|版\s*次)', '', cl)
            
            for splitter in noise_splitters:
                cl = re.split(splitter, cl, flags=re.IGNORECASE)[0]
            
            cl = cl.strip()
            if len(cl) > 2 and not re.match(r'^\d+\)\s*©.*', cl):
                cleaned_lines.append(cl)
                
        lines = cleaned_lines
        start_index = -1
        
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
        
        # ИЗМЕНЕНИЕ: Улучшенный паттерн (захватывает "6背面附胶" без точки после цифры)
        list_pattern = r'^\s*(?:[△∆▲A-Z]\s*)?(?:\d+|[lI\|])\s*(?:[\.\)\、\-\:]|(?=[\u4e00-\u9fa5])|\s+(?=[A-Za-z\u4e00-\u9fa5]))'
        
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
            # Резервный поиск, если не найден заголовок
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
        self.status_bar.showMessage("Идет анализ PDF и распознавание текста (RapidOCR)...")
        
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
            
            tech_req_list = [item.strip() for item in re.split(r'\n\s*\n', tech_req_text) if item.strip()]
            
            replacements = {
                "{SUPPLIER}": self.in_supplier.text(),
                "{PART_NAME}": self.in_part_name.text(),
                "{PART_NUMBER}": self.in_part_number.text(),
                "{MATERIAL}": self.in_material.text(),
            }
            
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
                        
                        modified = re.sub(r'\{\s+([^}]+?)\s+\}', r'{\1}', original)
                        
                        for key, val in replacements.items():
                            if key in modified:
                                modified = modified.replace(key, val)
                        
                        if modified != original:
                            cell.value = modified
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
