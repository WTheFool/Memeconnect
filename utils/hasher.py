import imagehash
from PIL import Image
import io
import torch
from torchvision import transforms

# Preprocessing must exactly match your train_model.py
preprocess = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

def generate_phash(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))
    return str(imagehash.phash(img))

def predict_meme(image_bytes, model):
    """Uses your meme_brain.pth to judge if an image is Safe (0) or Unsafe (1)."""
    img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    input_tensor = preprocess(img).unsqueeze(0)

    with torch.no_grad():
        output = model(input_tensor)
        # Returns the index of the highest score (e.g., 0 or 1)
        return torch.argmax(output, dim=1).item()
