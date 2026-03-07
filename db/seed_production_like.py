"""Seed the live Patra database with production-like data.

Truncates all tables and inserts 10 model cards (5 public, 5 private),
10 models, and 10 datasheets (5 public, 5 private).

Usage:
    DATABASE_URL="postgresql://…" python3 db/seed_production_like.py
"""

import asyncio
import os
import ssl

import asyncpg

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://patradb:zBQDRU23BVwoXh8zGh77eumDWOVR7c"
    "@patradb.pods.icicleai.tapis.io:443/patradb?sslmode=require",
)

# ── Model cards: 5 public + 5 private ────────────────────────────────────────
MODEL_CARDS = [
    # --- PUBLIC (5) ---
    {
        "id": "43d851cd-a509-49e3-8416-50b344b174ed",
        "name": "HybridEnd2EndLearner",
        "version": "5a",
        "is_private": False,
        "short_description": "HybridEnd2EndLearner 97% MNIST Dataset",
        "full_description": "End-to-end hybrid quantum-classical learner achieving 97% accuracy on the MNIST handwritten digit dataset.",
        "keywords": "hybrid,quantum,mnist,classification",
        "author": "nkarthikeyan",
        "citation": "Karthikeyan et al., 2024. HybridEnd2EndLearner for MNIST.",
        "input_data": "MNIST 28×28 grayscale images",
        "input_type": "images",
        "output_data": "digit class probabilities",
        "foundational_model": "HybridEnd2EndLearner",
        "category": "classification",
    },
    {
        "id": "41d3ed40-b836-4a62-b3fb-67cee79f33d9",
        "name": "MegaDetector for Wildlife Detection",
        "version": "5a",
        "is_private": False,
        "short_description": "Wildlife detection using MegaDetector from Microsoft.",
        "full_description": "MegaDetector v5a is a camera-trap image detector from Microsoft AI for Earth. It classifies images as containing animals, people, or vehicles.",
        "keywords": "wildlife,camera trap,megadetector,object detection",
        "author": "wqiu",
        "citation": "Beery et al., 2019. Efficient Pipeline for Camera Trap Image Review. arXiv:1907.06772",
        "input_data": "Camera trap images",
        "input_type": "images",
        "output_data": "Bounding boxes (animal, person, vehicle)",
        "foundational_model": "MegaDetector",
        "category": "detection",
    },
    {
        "id": "ec3f6227-14c5-4873-96d7-14ddcaf9b34a",
        "name": "GoogLeNet for Image Classification",
        "version": "1.0",
        "is_private": False,
        "short_description": "Image classification using GoogLeNet.",
        "full_description": "GoogLeNet (Inception v1) pre-trained on ImageNet for general-purpose image classification.",
        "keywords": "googlenet,inception,classification,imagenet",
        "author": "jstubbs",
        "citation": "Szegedy et al., 2015. Going Deeper with Convolutions. CVPR 2015.",
        "input_data": "https://image-net.org/",
        "input_type": "images",
        "output_data": "ImageNet class probabilities",
        "foundational_model": "GoogLeNet",
        "category": "classification",
    },
    {
        "id": "0556d19e-b478-4a89-bd74-a2d822e97a8a",
        "name": "ResNet50 Image Classification Model",
        "version": "1.0",
        "is_private": False,
        "short_description": "Pre-trained ResNet50 model from torchvision for image classification.",
        "full_description": "Pre-trained ResNet50 from torchvision, fine-tuned for general image classification benchmarks.",
        "keywords": "resnet50,classification,torchvision,imagenet",
        "author": "cgarcia",
        "citation": "He et al., 2016. Deep Residual Learning for Image Recognition. CVPR 2016.",
        "input_data": "https://image-net.org/",
        "input_type": "images",
        "output_data": "ImageNet class probabilities",
        "foundational_model": "ResNet50",
        "category": "classification",
    },
    {
        "id": "0cddbc64-75f7-4aee-a91d-c27583415bbc",
        "name": "Ultralytics YOLO",
        "version": "9e",
        "is_private": False,
        "short_description": "YOLOv9",
        "full_description": "YOLOv9 marks a significant advancement in real-time object detection, introducing groundbreaking techniques such as Programmable Gradient Information (PGI) and the Generalized Efficient Layer Aggregation Network (GELAN).",
        "keywords": "yolo, ultralytics, object detection",
        "author": "skhuvis",
        "citation": "YOLOv9: Learning What You Want to Learn Using Programmable Gradient Information by Wang, Chien-Yao and Liao, Hong-Yuan Mark (arXiv:2402.13616)",
        "input_data": "https://cocodataset.org/",
        "input_type": "images",
        "output_data": "",
        "foundational_model": "YOLOv5",
        "category": "classification",
    },
    # --- PRIVATE (5) ---
    {
        "id": "5356e5ba-b700-449a-ace3-ddecbce7a30a",
        "name": "MegaDetector for Wildlife Detection",
        "version": "5a (OSA finetuning)",
        "is_private": True,
        "short_description": "Wildlife detection using MegaDetector from Microsoft.",
        "full_description": "MegaDetector v5a fine-tuned on the OSA (Open Science Alliance) camera trap dataset.",
        "keywords": "wildlife,camera trap,megadetector,finetuned,osa",
        "author": "rcardone",
        "citation": "Beery et al., 2019. Efficient Pipeline for Camera Trap Image Review. arXiv:1907.06772",
        "input_data": "Camera trap images",
        "input_type": "images",
        "output_data": "Bounding boxes (animal, person, vehicle)",
        "foundational_model": "MegaDetector",
        "category": "detection",
    },
    {
        "id": "2983330b-28a4-4fb5-816d-aee0e421cb72",
        "name": "MegaDetector for Wildlife Detection",
        "version": "6b-yolov9c",
        "is_private": True,
        "short_description": "Wildlife detection using MegaDetector from Microsoft.",
        "full_description": "MegaDetector v6b built on YOLOv9c backbone for improved speed-accuracy trade-off.",
        "keywords": "wildlife,camera trap,megadetector,yolov9",
        "author": "wqiu",
        "citation": "Beery et al., 2019. Efficient Pipeline for Camera Trap Image Review. arXiv:1907.06772",
        "input_data": "Camera trap images",
        "input_type": "images",
        "output_data": "Bounding boxes (animal, person, vehicle)",
        "foundational_model": "YOLOv9c",
        "category": "detection",
    },
    {
        "id": "de221f7c-5c78-4375-b9f0-617884b75aa5",
        "name": "Yolo Object Detecion - for detecting a soft toy",
        "version": "yolo11l_ep1_bs32_lr0.005_8aa95a86.pt",
        "is_private": True,
        "short_description": "Detecting Soft toys in frame usining fine-tuned yolo model",
        "full_description": "YOLOv11-large fine-tuned to detect soft toys in camera frames for inventory counting.",
        "keywords": "yolo,object detection,soft toy,inventory",
        "author": "skhuvis",
        "citation": "",
        "input_data": "Camera frames",
        "input_type": "images",
        "output_data": "Bounding boxes with confidence",
        "foundational_model": "YOLOv11",
        "category": "detection",
    },
    {
        "id": "687437a9-aa0a-4255-a350-2cd6b822affd",
        "name": "Ultralytics YOLO26n",
        "version": "6b-yolov9c",
        "is_private": True,
        "short_description": "YOLO26n.",
        "full_description": "YOLO26 is the latest evolution in the YOLO series of real-time object detectors, engineered from the ground up for edge and low-power devices.",
        "keywords": "yolo, ultralytics, object detection",
        "author": "skhuvis",
        "citation": "https://huggingface.co/Ultralytics/YOLO26",
        "input_data": "https://cocodataset.org/",
        "input_type": "images",
        "output_data": "",
        "foundational_model": "YOLO26",
        "category": "classification",
    },
    {
        "id": "4e7f645d-9c64-4fc6-b67d-04eb0a4ce44a",
        "name": "Ultralytics YOLO26x",
        "version": "26x",
        "is_private": True,
        "short_description": "YOLO26x.",
        "full_description": "YOLO26x is the extra-large variant of YOLO26 designed for maximum accuracy on high-resolution inputs.",
        "keywords": "yolo, ultralytics, object detection, yolo26",
        "author": "skhuvis",
        "citation": "https://huggingface.co/Ultralytics/YOLO26",
        "input_data": "https://cocodataset.org/",
        "input_type": "images",
        "output_data": "",
        "foundational_model": "YOLO26",
        "category": "classification",
    },
]

# ── Models (1:1 with model cards) ────────────────────────────────────────────
MODELS = [
    {"id": "43d851cd-a509-49e3-8416-50b344b174ed-model", "name": "HybridEnd2EndLearner", "version": "5a", "description": "Hybrid quantum-classical model for digit classification.", "owner": "ICICLE", "location": "", "license": "MIT", "framework": "PennyLane", "model_type": "hybrid quantum-classical", "test_accuracy": 0.97, "model_card_id": "43d851cd-a509-49e3-8416-50b344b174ed"},
    {"id": "41d3ed40-b836-4a62-b3fb-67cee79f33d9-model", "name": "MegaDetector", "version": "5a", "description": "Camera-trap animal/person/vehicle detector.", "owner": "Microsoft AI for Earth", "location": "https://github.com/microsoft/CameraTraps/releases/download/v5.0/md_v5a.0.0.pt", "license": "MIT", "framework": "PyTorch", "model_type": "convolutional neural network", "test_accuracy": 0.89, "model_card_id": "41d3ed40-b836-4a62-b3fb-67cee79f33d9"},
    {"id": "ec3f6227-14c5-4873-96d7-14ddcaf9b34a-model", "name": "GoogLeNet", "version": "1.0", "description": "Inception v1 pre-trained on ImageNet.", "owner": "torchvision", "location": "", "license": "BSD-3-Clause", "framework": "PyTorch", "model_type": "convolutional neural network", "test_accuracy": 0.74, "model_card_id": "ec3f6227-14c5-4873-96d7-14ddcaf9b34a"},
    {"id": "0556d19e-b478-4a89-bd74-a2d822e97a8a-model", "name": "ResNet50", "version": "1.0", "description": "Pre-trained ResNet50 from torchvision.", "owner": "torchvision", "location": "", "license": "BSD-3-Clause", "framework": "PyTorch", "model_type": "convolutional neural network", "test_accuracy": 0.76, "model_card_id": "0556d19e-b478-4a89-bd74-a2d822e97a8a"},
    {"id": "0cddbc64-75f7-4aee-a91d-c27583415bbc-model", "name": "YOLO", "version": "9e", "description": "A convolutional neural network model for object detection.", "owner": "Ultralytics", "location": "https://github.com/ultralytics/assets/releases/download/v8.4.0/yolov9e.pt", "license": "AGPL-3.0 License", "framework": "PyTorch", "model_type": "convolutional neural network", "test_accuracy": 0.85, "model_card_id": "0cddbc64-75f7-4aee-a91d-c27583415bbc"},
    {"id": "5356e5ba-b700-449a-ace3-ddecbce7a30a-model", "name": "MegaDetector", "version": "5a-osa", "description": "OSA fine-tuned MegaDetector v5a.", "owner": "ICICLE", "location": "", "license": "MIT", "framework": "PyTorch", "model_type": "convolutional neural network", "test_accuracy": 0.92, "model_card_id": "5356e5ba-b700-449a-ace3-ddecbce7a30a"},
    {"id": "2983330b-28a4-4fb5-816d-aee0e421cb72-model", "name": "MegaDetector", "version": "6b-yolov9c", "description": "YOLOv9c backbone for better speed-accuracy.", "owner": "Microsoft AI for Earth", "location": "", "license": "MIT", "framework": "PyTorch", "model_type": "convolutional neural network", "test_accuracy": 0.90, "model_card_id": "2983330b-28a4-4fb5-816d-aee0e421cb72"},
    {"id": "de221f7c-5c78-4375-b9f0-617884b75aa5-model", "name": "YOLO11L SoftToy", "version": "yolo11l_ep1_bs32_lr0.005", "description": "YOLOv11-large fine-tuned for soft toy detection.", "owner": "skhuvis", "location": "", "license": "AGPL-3.0 License", "framework": "PyTorch", "model_type": "convolutional neural network", "test_accuracy": 0.82, "model_card_id": "de221f7c-5c78-4375-b9f0-617884b75aa5"},
    {"id": "687437a9-aa0a-4255-a350-2cd6b822affd-model", "name": "YOLO", "version": "26n", "description": "A convolutional neural network model for object detection.", "owner": "Ultralytics", "location": "https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n.pt", "license": "AGPL-3.0 License", "framework": "PyTorch", "model_type": "convolutional neural network", "test_accuracy": 0.85, "model_card_id": "687437a9-aa0a-4255-a350-2cd6b822affd"},
    {"id": "4e7f645d-9c64-4fc6-b67d-04eb0a4ce44a-model", "name": "YOLO", "version": "26x", "description": "Extra-large YOLO26 for maximum accuracy.", "owner": "Ultralytics", "location": "https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26x.pt", "license": "AGPL-3.0 License", "framework": "PyTorch", "model_type": "convolutional neural network", "test_accuracy": 0.88, "model_card_id": "4e7f645d-9c64-4fc6-b67d-04eb0a4ce44a"},
]

# ── Datasheets: 5 public + 5 private ─────────────────────────────────────────
DATASHEETS = [
    # --- PUBLIC (5) ---
    {"identifier": 1, "creator": "Microsoft AI for Earth", "title": "LILA Camera Traps", "publisher": "LILA BC", "publication_year": 2021, "resource_type": "images", "size": "3 TB", "format": "jpeg", "version": "1.0", "rights": "public", "description": "Labelled camera-trap images from LILA BC.", "geo_location": "global", "category": "wildlife", "is_private": False, "model_card_id": "41d3ed40-b836-4a62-b3fb-67cee79f33d9"},
    {"identifier": 2, "creator": "torchvision", "title": "ImageNet-1K", "publisher": "Stanford / Princeton", "publication_year": 2012, "resource_type": "images", "size": "150 GB", "format": "jpeg", "version": "1.0", "rights": "academic", "description": "1000-class subset of the ImageNet dataset.", "geo_location": "global", "category": "classification", "is_private": False, "model_card_id": "ec3f6227-14c5-4873-96d7-14ddcaf9b34a"},
    {"identifier": 3, "creator": "Yann LeCun", "title": "MNIST", "publisher": "NYU", "publication_year": 1998, "resource_type": "images", "size": "50 MB", "format": "idx", "version": "1.0", "rights": "public", "description": "Handwritten digit images 0-9.", "geo_location": "global", "category": "classification", "is_private": False, "model_card_id": "43d851cd-a509-49e3-8416-50b344b174ed"},
    {"identifier": 4, "creator": "COCO Consortium", "title": "MS COCO 2017", "publisher": "cocodataset.org", "publication_year": 2017, "resource_type": "images", "size": "25 GB", "format": "jpeg", "version": "2017", "rights": "CC BY 4.0", "description": "Common Objects in Context detection/segmentation dataset.", "geo_location": "global", "category": "detection", "is_private": False, "model_card_id": "0cddbc64-75f7-4aee-a91d-c27583415bbc"},
    {"identifier": 5, "creator": "torchvision", "title": "ImageNet ResNet Subset", "publisher": "Stanford / Princeton", "publication_year": 2015, "resource_type": "images", "size": "12 GB", "format": "jpeg", "version": "1.0", "rights": "academic", "description": "Curated ImageNet subset for ResNet50 benchmarking.", "geo_location": "global", "category": "classification", "is_private": False, "model_card_id": "0556d19e-b478-4a89-bd74-a2d822e97a8a"},
    # --- PRIVATE (5) ---
    {"identifier": 6, "creator": "ICICLE", "title": "OSA Camera Traps", "publisher": "Open Science Alliance", "publication_year": 2024, "resource_type": "images", "size": "18 GB", "format": "jpeg", "version": "1.0", "rights": "research-only", "description": "OSA partner camera-trap imagery for fine-tuning.", "geo_location": "US", "category": "wildlife", "is_private": True, "model_card_id": "5356e5ba-b700-449a-ace3-ddecbce7a30a"},
    {"identifier": 7, "creator": "ICICLE", "title": "ENA Wildlife Survey", "publisher": "ICICLE", "publication_year": 2024, "resource_type": "images", "size": "32 GB", "format": "jpeg", "version": "1.0", "rights": "research-only", "description": "Endangered North American species camera-trap survey.", "geo_location": "US", "category": "wildlife", "is_private": True, "model_card_id": "2983330b-28a4-4fb5-816d-aee0e421cb72"},
    {"identifier": 8, "creator": "skhuvis", "title": "Soft Toy Inventory Frames", "publisher": "Internal", "publication_year": 2025, "resource_type": "images", "size": "2 GB", "format": "jpeg", "version": "1.0", "rights": "internal", "description": "Camera frames labelled with soft-toy bounding boxes.", "geo_location": "US", "category": "detection", "is_private": True, "model_card_id": "de221f7c-5c78-4375-b9f0-617884b75aa5"},
    {"identifier": 9, "creator": "Ultralytics", "title": "YOLO26 Edge Benchmark", "publisher": "Ultralytics", "publication_year": 2025, "resource_type": "images", "size": "8 GB", "format": "jpeg", "version": "1.0", "rights": "internal", "description": "Edge device evaluation images for YOLO26n benchmarking.", "geo_location": "global", "category": "detection", "is_private": True, "model_card_id": "687437a9-aa0a-4255-a350-2cd6b822affd"},
    {"identifier": 10, "creator": "Ultralytics", "title": "YOLO26x High-Res Evaluation", "publisher": "Ultralytics", "publication_year": 2025, "resource_type": "images", "size": "45 GB", "format": "png", "version": "1.0", "rights": "internal", "description": "High-resolution evaluation set for YOLO26x accuracy testing.", "geo_location": "global", "category": "detection", "is_private": True, "model_card_id": "4e7f645d-9c64-4fc6-b67d-04eb0a4ce44a"},
]

USERS = ["nkarthikeyan", "wqiu", "jstubbs", "cgarcia", "rcardone", "skhuvis"]
EDGE_DEVICES = ["jetson_nano_01", "rpi4_cam_01", "coral_tpu_01"]


async def seed():
    dsn = DATABASE_URL.replace(":5432", ":443").split("?")[0]
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    conn = await asyncpg.connect(dsn, ssl=ctx, timeout=30)
    print("Connected.")

    async with conn.transaction():
        for t in [
            "experiment_images", "deployments", "experiments", "raw_images",
            "datasheets", "models", "model_cards", "dataset_schemas",
            "edge_devices", "users",
        ]:
            await conn.execute(f"TRUNCATE TABLE {t} CASCADE")
        print("Truncated all tables.")

        await conn.executemany("INSERT INTO users (id) VALUES ($1)", [(u,) for u in USERS])
        await conn.executemany("INSERT INTO edge_devices (id) VALUES ($1)", [(d,) for d in EDGE_DEVICES])

        await conn.executemany(
            """INSERT INTO model_cards (
                id, name, version, is_private,
                short_description, full_description,
                keywords, author, citation,
                input_data, input_type, output_data,
                foundational_model, category, documentation
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,'')""",
            [
                (
                    mc["id"], mc["name"], mc["version"], mc["is_private"],
                    mc["short_description"], mc["full_description"],
                    mc["keywords"], mc["author"], mc["citation"],
                    mc["input_data"], mc["input_type"], mc["output_data"],
                    mc.get("foundational_model", ""), mc.get("category", ""),
                )
                for mc in MODEL_CARDS
            ],
        )
        print(f"Inserted {len(MODEL_CARDS)} model cards.")

        await conn.executemany(
            """INSERT INTO models (
                id, name, version, description, owner, location,
                license, framework, model_type, test_accuracy, model_card_id
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)""",
            [
                (
                    m["id"], m["name"], m["version"], m["description"],
                    m["owner"], m["location"], m["license"], m["framework"],
                    m["model_type"], m["test_accuracy"], m["model_card_id"],
                )
                for m in MODELS
            ],
        )
        print(f"Inserted {len(MODELS)} models.")

        await conn.executemany(
            """INSERT INTO datasheets (
                identifier, creator, title, publisher, publication_year,
                resource_type, size, format, version, rights, description,
                geo_location, category, is_private, model_card_id
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)""",
            [
                (
                    ds["identifier"], ds["creator"], ds["title"],
                    ds["publisher"], ds["publication_year"],
                    ds["resource_type"], ds["size"], ds["format"],
                    ds["version"], ds["rights"], ds["description"],
                    ds["geo_location"], ds["category"], ds["is_private"],
                    ds["model_card_id"],
                )
                for ds in DATASHEETS
            ],
        )
        print(f"Inserted {len(DATASHEETS)} datasheets.")

    await conn.close()
    print("Done – 10 model cards, 10 models, 10 datasheets (5 public / 5 private each).")


if __name__ == "__main__":
    asyncio.run(seed())
