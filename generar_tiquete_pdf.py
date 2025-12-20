#!/usr/bin/env python3
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
import json
import sys
import os
from datetime import datetime

def generar_tiquete_pdf(tiquete_data, output_dir="/data/tiquetes_pdf"):
    # Crear directorio si no existe
    os.makedirs(output_dir, exist_ok=True)

    # Nombre del archivo
    numero = tiquete_data['numero']
    fecha_obj = datetime.now()
    year = fecha_obj.strftime('%Y')
    month = fecha_obj.strftime('%m')

    # Crear estructura de carpetas por año/mes
    pdf_dir = os.path.join(output_dir, year, month)
    os.makedirs(pdf_dir, exist_ok=True)

    filename = f"tiquete_{numero:04d}.pdf"
    filepath = os.path.join(pdf_dir, filename)

    # Crear PDF
    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter

    # Configuración
    margin = 0.75 * inch
    y = height - margin

    # ==================== ENCABEZADO ====================
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width/2, y, "TERMINAL GALÁN")
    y -= 0.3 * inch

    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width/2, y, "TIQUETE DE RECEPCIÓN DE GLP")
    y -= 0.5 * inch

    # Línea separadora
    c.setLineWidth(2)
    c.line(margin, y, width - margin, y)
    y -= 0.4 * inch

    # ==================== INFORMACIÓN GENERAL ====================
    c.setFont("Helvetica-Bold", 11)
    info_data = [
        ["Tiquete No.:", str(tiquete_data['numero'])],
        ["Fecha y Hora:", tiquete_data['fecha']],
        ["Producto:", tiquete_data['producto']],
        ["Operador:", tiquete_data.get('operador', 'Sistema Automatizado')]
    ]

    for label, value in info_data:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin, y, label)
        c.setFont("Helvetica", 11)
        c.drawString(margin + 2*inch, y, value)
        y -= 0.25 * inch

    y -= 0.3 * inch

    # ==================== DATOS DE RECEPCIÓN ====================
    # Título de la sección
    c.setFillColor(colors.HexColor('#3498db'))
    c.rect(margin, y - 0.05*inch, width - 2*margin, 0.35*inch, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width/2, y + 0.05*inch, "DATOS DE RECEPCIÓN")
    c.setFillColor(colors.black)
    y -= 0.5 * inch

    # Datos en tabla
    datos = tiquete_data['datos']

    data_table = [
        ["Volumen (Litros):", f"{datos['volumen_litros']:,.0f} L"],
        ["Volumen (m³):", f"{datos['volumen_m3']} m³"],
        ["Densidad (kg/m³):", f"{datos['densidad']:.2f} kg/m³"],
        ["Peso Neto (kg):", f"{datos['peso_kg']} kg"],
        ["Temperatura (°F):", f"{datos['temperatura']:.1f} °F"],
        ["Presión (PSI):", f"{datos['presion']:.1f} PSI"],
        ["Flujo Promedio (m³/h):", f"{datos['flujo_promedio']:.1f} m³/h"]
    ]

    for label, value in data_table:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(margin + 0.2*inch, y, label)
        c.setFont("Helvetica", 10)
        c.drawRightString(width - margin - 0.2*inch, y, value)

        # Línea punteada
        c.setDash(2, 2)
        c.setLineWidth(0.5)
        c.line(margin, y - 0.05*inch, width - margin, y - 0.05*inch)
        c.setDash()

        y -= 0.3 * inch

    y -= 0.3 * inch

    # ==================== OBSERVACIONES ====================
    c.setLineWidth(1)
    c.line(margin, y, width - margin, y)
    y -= 0.3 * inch

    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Observaciones:")
    y -= 0.25 * inch

    # Caja de observaciones
    obs_height = 0.8 * inch
    c.rect(margin, y - obs_height, width - 2*margin, obs_height)

    c.setFont("Helvetica", 10)
    observaciones = tiquete_data.get('observaciones', 'Recepción automatizada - Sin observaciones')
    c.drawString(margin + 0.1*inch, y - 0.25*inch, observaciones)

    y -= obs_height + 0.5*inch

    # ==================== FIRMAS ====================
    y = 2.5 * inch

    # Líneas de firma
    firma_width = 2.5 * inch
    firma_x1 = margin + 0.5*inch
    firma_x2 = width - margin - firma_width - 0.5*inch

    c.setLineWidth(1.5)
    c.line(firma_x1, y, firma_x1 + firma_width, y)
    c.line(firma_x2, y, firma_x2 + firma_width, y)

    y -= 0.25 * inch

    c.setFont("Helvetica", 10)
    c.drawCentredString(firma_x1 + firma_width/2, y, "Entregado por")
    c.drawCentredString(firma_x2 + firma_width/2, y, "Recibido por")

    # ==================== PIE DE PÁGINA ====================
    c.setFont("Helvetica", 8)
    c.drawCentredString(width/2, 0.5*inch,
        f"Documento generado automáticamente - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Guardar PDF
    c.save()

    print(json.dumps({
        "success": True,
        "filepath": filepath,
        "filename": filename
    }))

    return filepath

if __name__ == "__main__":
    # Leer datos desde stdin
    input_data = sys.stdin.read()
    tiquete = json.loads(input_data)

    # Asegurar que el directorio existe
    output_dir = os.getenv('PDF_OUTPUT_DIR', '/data/tiquetes_pdf')

    try:
        filepath = generar_tiquete_pdf(tiquete, output_dir)
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": str(e)
        }), file=sys.stderr)
        sys.exit(1)
