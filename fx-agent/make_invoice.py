from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
OUT = r"C:\Users\Monalisha Ojha\Downloads\invoice.pdf"
c = canvas.Canvas(OUT, pagesize=A4); W, H = A4
def t(x,y,s,sz=10,f="Helvetica",col=colors.black):
    c.setFillColor(col); c.setFont(f,sz); c.drawString(x,y,s)
t(20*mm,H-25*mm,"INVOICE",24,"Helvetica-Bold",colors.HexColor("#1a2b6b"))
t(20*mm,H-33*mm,"Invoice No: INV-2026-0042",10)
t(20*mm,H-39*mm,"Issue date: 2026-06-21",10)
t(20*mm,H-45*mm,"Due date:   2026-07-05",10,"Helvetica-Bold",colors.HexColor("#b00020"))
c.setStrokeColor(colors.HexColor("#cccccc")); c.line(20*mm,H-50*mm,W-20*mm,H-50*mm)
t(20*mm,H-60*mm,"From (Sender / Payer)",9,"Helvetica-Bold",colors.HexColor("#666666"))
t(20*mm,H-67*mm,"Alice GmbH",11,"Helvetica-Bold")
t(20*mm,H-73*mm,"Friedrichstrasse 12, 10117 Berlin, Germany",9)
t(110*mm,H-60*mm,"To (Receiver / Payee)",9,"Helvetica-Bold",colors.HexColor("#666666"))
t(110*mm,H-67*mm,"Bob Textiles S.A. de C.V.",11,"Helvetica-Bold")
t(110*mm,H-73*mm,"Polanco, Mexico City 11560, Mexico",9)
y=H-90*mm; c.setFillColor(colors.HexColor("#1a2b6b")); c.rect(20*mm,y,W-40*mm,8*mm,fill=1,stroke=0)
t(23*mm,y+2.5*mm,"Description",10,"Helvetica-Bold",colors.white); t(150*mm,y+2.5*mm,"Amount",10,"Helvetica-Bold",colors.white)
y-=9*mm; t(23*mm,y,"Consulting services (June 2026)",10); t(150*mm,y,"50.00 MXN",10)
y-=7*mm; c.line(20*mm,y,W-20*mm,y); y-=7*mm
t(120*mm,y,"Total due:",12,"Helvetica-Bold"); t(150*mm,y,"50.00 MXN",12,"Helvetica-Bold")
y-=18*mm; t(20*mm,y,"Payment Instructions",11,"Helvetica-Bold",colors.HexColor("#1a2b6b")); y-=7*mm
t(20*mm,y,"Pay in: MXN (Mexican Peso)",10); y-=6*mm
t(20*mm,y,"Receiver bank - XRPL settlement address (payee):",10,"Helvetica-Bold"); y-=6*mm
t(20*mm,y,"rH1cw3garj1Eu7BrPP1ssDH1s2veERN397",11,"Courier-Bold",colors.HexColor("#0a6b2b")); y-=8*mm
t(20*mm,y,"Receiver bank fiat details (off-chain off-ramp):",10,"Helvetica-Bold"); y-=6*mm
t(20*mm,y,"CLABE: 012 180 0123456789 5",10,"Courier")
t(20*mm,18*mm,"Thank you for your business. Settlement via XRPL.",9,"Helvetica-Oblique",colors.HexColor("#888888"))
c.showPage(); c.save(); print("created MXN invoice:",OUT)
