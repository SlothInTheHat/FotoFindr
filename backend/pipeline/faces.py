def get_face_emotions(image_path: str):
    try:
        import numpy as np
        from PIL import Image
        from deepface import DeepFace  # lazy import — keeps server bootable if dep is broken

        # Pre-load with PIL → numpy to bypass DeepFace's internal OpenCV file reader,
        # which can fail on Windows paths or certain JPEG variants.
        img_array = np.array(Image.open(image_path).convert("RGB"))

        results = DeepFace.analyze(
            img_path=img_array,
            actions=['emotion'],
            detector_backend='retinaface',
            align=True,
            expand_percentage=10,
        )
        return results
    except Exception as e:
        return {"error": str(e)}