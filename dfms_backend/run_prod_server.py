import os
from waitress import serve
from dfms_backend.wsgi import application

if __name__ == '__main__':
    print("Starting production server on http://localhost:8004...")
    # You can adjust threads to handle more concurrent users
    serve(application, host='0.0.0.0', port=8000, threads=4)