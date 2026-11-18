
from PIL import Image, ImageDraw, ImageFont

# Create a white document image
image = Image.new("RGB", (1200, 650), "white")
draw = ImageDraw.Draw(image)

# Use a standard Windows font
font_path = "C:/Windows/Fonts/arial.ttf"

title_font = ImageFont.truetype(font_path, 42)
heading_font = ImageFont.truetype(font_path, 30)
body_font = ImageFont.truetype(font_path, 26)

# Document content
draw.text((60, 40), "CIABOC", fill="black", font=title_font)
draw.text(
    (60, 110),
    "RECEPTION MANAGEMENT",
    fill="black",
    font=heading_font
)

draw.line((60, 165, 1100, 165), fill="black", width=3)

draw.text(
    (60, 210),
    "VISITOR INFORMATION",
    fill="black",
    font=heading_font
)

draw.text((60, 280), "Visitor ID: TEST-001", fill="black", font=body_font)
draw.text((60, 340), "Name: JOHN DOE", fill="black", font=body_font)
draw.text((60, 400), "Document Type: TEST DOCUMENT", fill="black", font=body_font)
draw.text((60, 460), "Date: 18 NOVEMBER 2026", fill="black", font=body_font)

# Save synthetic test image
image.save("samples/test_visitor.png")

print("Synthetic test image created successfully!")
