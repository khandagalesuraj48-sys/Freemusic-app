
import sys

from pathlib import Path



ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:

    sys.path.insert(0, str(ROOT))



from app import app



_original_wsgi = app.wsgi_app



def vercel_wsgi(environ, start_response):

    path = environ.get("PATH_INFO", "")

    if path == "/api/index" or path == "/api/index/":

        environ["PATH_INFO"] = "/result/"

    return _original_wsgi(environ, start_response)



app.wsgi_app = vercel_wsgi

