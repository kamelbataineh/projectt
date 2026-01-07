import os
import numpy as np
import tensorflow as tf
import cv2
from tensorflow.keras.preprocessing import image as keras_image
from tensorflow.keras.applications.efficientnet_v2 import preprocess_input as preprocess_efficientnet_v2
import base64


IMG_SIZE = 456
CLASS_NAMES = ["benign", "malignant", "normal"]


def load_original_rgb(img_path):
    img = keras_image.load_img(img_path, target_size=(IMG_SIZE, IMG_SIZE))
    img = img.convert("RGB")  # <- تأكد من 3 قنوات
    return keras_image.img_to_array(img).astype(np.uint8)

def load_preprocessed(img_path):
    img = keras_image.load_img(img_path, target_size=(IMG_SIZE, IMG_SIZE))
    img = img.convert("RGB")  # <- تأكد من 3 قنوات
    x = keras_image.img_to_array(img).astype(np.float32)
    x = np.expand_dims(x, axis=0)
    x = preprocess_efficientnet_v2(x)
    return x



def find_last_conv_layer(model):
    for layer in reversed(model.layers):
        if isinstance(layer, (tf.keras.layers.Conv2D,
                              tf.keras.layers.DepthwiseConv2D)):
            return layer.name
        if isinstance(layer, tf.keras.Model):
            name = find_last_conv_layer(layer)
            if name:
                return name
    return None


def gradcam(model, x, class_index):
    from tensorflow.keras.models import Model
    import tensorflow as tf

    if len(x.shape) == 3:
        x = tf.expand_dims(x, axis=0)

    last_conv_name = find_last_conv_layer(model)
    last_conv_layer = model.get_layer(last_conv_name)

    grad_model = Model(
        inputs=model.inputs,
        outputs=[last_conv_layer.output, model.output]
    )

    with tf.GradientTape() as tape:
        conv_outputs, predictions = grad_model(
            {"input_layer_1": x}
        )

        if isinstance(predictions, list):
            predictions = predictions[0]

        loss = predictions[0, class_index]

    grads = tape.gradient(loss, conv_outputs)
    pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))

    conv_outputs = conv_outputs[0]
    heatmap = tf.reduce_sum(conv_outputs * pooled_grads, axis=-1)

    heatmap = tf.maximum(heatmap, 0)
    heatmap /= tf.reduce_max(heatmap) + 1e-8

    return heatmap.numpy(), last_conv_name




def get_bbox_from_heatmap(heatmap, thresh=0.80, use_largest_cc=True):
    mask = (heatmap >= thresh).astype(np.uint8)

    if mask.sum() == 0:
        return None

    if use_largest_cc:
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        if num_labels <= 1:
            return None

        largest = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
        mask = (labels == largest).astype(np.uint8)

        if mask.sum() == 0:
            return None

    ys, xs = np.where(mask == 1)
    y1, y2 = int(ys.min()), int(ys.max())
    x1, x2 = int(xs.min()), int(xs.max())
    return x1, y1, x2, y2


def overlay_heatmap_and_box(img, heatmap, alpha=0.35, thresh=0.80):
    heatmap = cv2.resize(heatmap, (img.shape[1], img.shape[0]))
    heatmap_uint8 = np.uint8(255 * heatmap)

    heatmap_color = cv2.applyColorMap(heatmap_uint8, cv2.COLORMAP_JET)
    heatmap_color = cv2.cvtColor(heatmap_color, cv2.COLOR_BGR2RGB)

    overlay = cv2.addWeighted(img, 1 - alpha, heatmap_color, alpha, 0)

    bbox = get_bbox_from_heatmap(heatmap, thresh=thresh, use_largest_cc=True)
    if bbox:
        x1, y1, x2, y2 = bbox
        cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 255, 0), 4)

    return heatmap_color, overlay



def array_to_base64(img_array):
    # img_array = RGB uint8
    _, buffer = cv2.imencode(".png", cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR))
    img_bytes = buffer.tobytes()
    img_b64 = base64.b64encode(img_bytes).decode("utf-8")
    return img_b64






def predict_and_explain(model, img_path):
    orig = load_original_rgb(img_path)
    x = load_preprocessed(img_path)

    probs = model.predict(
        {"input_layer_1": x},
        verbose=0
    )[0]

    pred_idx = int(np.argmax(probs))
    pred_label = CLASS_NAMES[pred_idx]

    heatmap, conv_name = gradcam(model, x, pred_idx)
    heatmap_img, overlay = overlay_heatmap_and_box(orig, heatmap)

    return {
        "pred_label": pred_label,
        "probs": probs.tolist(),
        "overlay": array_to_base64(overlay),
        "heatmap": array_to_base64(heatmap_img),
        "last_conv": conv_name
    }
