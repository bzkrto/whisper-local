"""Use configured proxy trust without weakening provider TLS verification."""
import os
import ssl
from pathlib import Path


def configure_edge_tls():
    bundle=os.environ.get('SSL_CERT_FILE') or os.environ.get('REQUESTS_CA_BUNDLE')
    if not bundle: return
    if not Path(bundle).is_file(): raise OSError('Yapılandırılmış TLS sertifika dosyası bulunamadı.')
    # edge-tts supplies its own certifi context; extend it with the configured CA.
    import edge_tts.communicate
    import edge_tts.voices
    for module in (edge_tts.communicate,edge_tts.voices):
        context=getattr(module,'_SSL_CTX',None)
        if isinstance(context,ssl.SSLContext): context.load_verify_locations(cafile=bundle)
