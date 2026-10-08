# Local face-match setup

Workforce uses the local OpenCV YuNet + SFace adapter. It is disabled by
default. Do not enable the attendance-policy switch until the provider health
check and a small employee validation set pass.

Install the optional dependency in the bench environment:

```bash
./env/bin/pip install -e './apps/workforce_suite[face-match]'
```

Store the pinned models under the site directory, for example:

```text
sites/hrms.localhost/private/files/workforce_face_models/face_detection_yunet_2023mar.onnx
sites/hrms.localhost/private/files/workforce_face_models/face_recognition_sface_2021dec.onnx
```

The current verified SHA-256 values are:

```text
8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4  face_detection_yunet_2023mar.onnx
0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79  face_recognition_sface_2021dec.onnx
```

Configure `Workforce Face Match Settings` with paths relative to the site:

```text
private/files/workforce_face_models/face_detection_yunet_2023mar.onnx
private/files/workforce_face_models/face_recognition_sface_2021dec.onnx
```

The baseline cosine threshold is `0.363`; it must be validated against
Workforce's own staff/device/lighting conditions before use. A mismatch is
recorded as evidence and does not silently deduct pay. Browser GPS and a
selfie are evidence, not mathematically perfect proof of identity or
liveness.
