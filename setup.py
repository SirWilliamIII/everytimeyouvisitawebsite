from setuptools import setup


APP = ['app.py']
OPTIONS = {
    'argv_emulation': True,
    'includes': ['PIL.Image'],
    'packages': ['sounddevice', 'scipy', 'cv2'],
    'plist': {
        'CFBundleName': 'Markdown Enhancer',
        'CFBundleDisplayName': 'Markdown Enhancer',
        'CFBundleIdentifier': 'com.markdown.enhancer',
        'CFBundleVersion': '1.0.3',
        'CFBundleShortVersionString': '1.0.3',
    },
}

setup(
    app=APP,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
