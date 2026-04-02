import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import datasets, models, transforms
import os
import time  # Import time for metrics

# --- SETTINGS ---
DATA_DIR = './training_data'
MODEL_SAVE_PATH = 'meme_brain.pth'
BATCH_SIZE = 128
MAX_EPOCHS = 50


def train():
    # 0. User Input for Target Range
    print("🎯 Setting Target Range (Default: 0.2 - 0.4)")
    try:
        val_min = input("Enter Minimum Loss (Stop immediately): ")
        LOSS_MIN = float(val_min) if val_min.strip() else 0.2
        val_max = input("Enter Maximum Loss (Vibe threshold): ")
        LOSS_MAX = float(val_max) if val_max.strip() else 0.4
    except ValueError:
        LOSS_MIN, LOSS_MAX = 0.2, 0.4

    # 1. Setup Device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"⚙️ Hardware: {device}")
    if device.type == 'cuda':
        print(f"🚀 SUCCESS! Using {torch.cuda.get_device_name(0)}")

    # 2. Data Loading & Weights
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])

    dataset = datasets.ImageFolder(DATA_DIR, transform=transform)
    train_loader = torch.utils.data.DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

    counts = [0] * len(dataset.classes)
    for _, label in dataset.samples: counts[label] += 1
    weights = [len(dataset) / (len(dataset.classes) * c) if c > 0 else 1.0 for c in counts]
    class_weights = torch.FloatTensor(weights).to(device)

    # 3. Model Setup
    model = models.mobilenet_v2(weights='DEFAULT')
    for param in model.parameters(): param.requires_grad = False

    num_ftrs = model.classifier[1].in_features
    model.classifier = nn.Sequential(nn.Dropout(0.2), nn.Linear(num_ftrs, 2))
    model = model.to(device)

    criterion = nn.CrossEntropyLoss(weight=class_weights)
    optimizer = optim.Adam(model.classifier.parameters(), lr=0.001)

    # 4. Training with Time Metrics
    print(f"🔥 Training started... Target Range: {LOSS_MIN} to {LOSS_MAX}")

    total_start_time = time.time()  # Start total timer

    try:
        for epoch in range(MAX_EPOCHS):
            epoch_start_time = time.time()  # Start epoch timer
            model.train()
            running_loss = 0.0

            for inputs, labels in train_loader:
                inputs, labels = inputs.to(device), labels.to(device)
                optimizer.zero_grad()
                outputs = model(inputs)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()
                running_loss += loss.item()

            avg_loss = running_loss / len(train_loader)
            epoch_duration = time.time() - epoch_start_time  # Calculate epoch duration

            print(f"✅ Epoch {epoch + 1} - Loss: {avg_loss:.4f} | Time: {epoch_duration:.2f}s")

            if avg_loss <= LOSS_MIN:
                print(f"🛑 Critical Low ({LOSS_MIN}) reached!")
                break
            elif avg_loss <= LOSS_MAX:
                print(f"✨ Vibe Target ({LOSS_MAX}) reached!")
                break

    except KeyboardInterrupt:
        print("\n🛑 Manual stop detected.")

    total_duration = time.time() - total_start_time  # Calculate total time
    print(f"\n✨ Training Complete!")
    print(f"⏱️ Total Time Taken: {total_duration / 60:.2f} minutes")

    torch.save(model.state_dict(), MODEL_SAVE_PATH)
    print(f"💾 Brain saved to '{MODEL_SAVE_PATH}'")


if __name__ == "__main__":
    train()
