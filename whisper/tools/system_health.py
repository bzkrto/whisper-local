"""Read-only resource snapshot. No process termination, shell or cloud calls."""
from datetime import datetime, timezone
from pathlib import Path


def collect_snapshot(metrics=None):
    if metrics is None:
        import psutil as metrics
    cpu = float(metrics.cpu_percent(interval=1.0))
    ram = metrics.virtual_memory()
    disk = metrics.disk_usage(str(Path.home()))
    processes = []
    skipped = 0
    for process in metrics.process_iter(['pid', 'name', 'memory_percent']):
        try:
            info = process.info
            memory = float(info.get('memory_percent') or 0)
            name = str(info.get('name') or 'İsimsiz uygulama')
            name = ''.join(c for c in name if c.isprintable())[:80]
            processes.append({'pid': info['pid'], 'name': name, 'memory_percent': round(memory,1)})
        except (metrics.Error, KeyError, TypeError, ValueError):
            skipped += 1
    return {
        'measured_at': datetime.now(timezone.utc).isoformat(),
        'cpu_percent': cpu,
        'ram_percent': float(ram.percent),
        'ram_total_gb': round(ram.total / 1024**3,1),
        'ram_available_gb': round(ram.available / 1024**3,1),
        'disk_path': str(Path.home()),
        'disk_free_gb': round(disk.free / 1024**3,1),
        'disk_free_percent': disk.free / disk.total * 100 if disk.total else None,
        'top_memory_processes': sorted(processes,key=lambda p:p['memory_percent'],reverse=True)[:3],
        'skipped_processes': skipped,
        'sample_seconds': 1,
    }


def summarize_snapshot(snapshot):
    cpu, ram = snapshot['cpu_percent'], snapshot['ram_percent']
    answer = f"Ölçüm: işlemci yüzde {cpu:.0f}, bellek yüzde {ram:.0f} dolu. Kullanıcı klasörünün bulunduğu diskte {snapshot['disk_free_gb']:.0f} gigabayt boş alan var."
    suggestions = []
    if cpu >= 90:
        suggestions.append('Bu ölçümde işlemci kullanımı yüksek; Görev Yöneticisi’nde işlemci sütununu kontrol et.')
    if ram >= 90:
        suggestions.append('Bellek kullanımı yüksek; kullanmadığın uygulama ve tarayıcı sekmelerini gözden geçir.')
    free_percent = snapshot['disk_free_percent']
    if free_percent is not None and free_percent < 10:
        suggestions.append('Diskte boş alan az; silmeden önce büyük dosyaları ve yedeklerini gözden geçir.')
    if suggestions:
        answer += ' ' + ' '.join(suggestions)
    else:
        answer += 'Bu örnekte işlemci, bellek veya boş disk alanı için eşik aşımı yok.'
    answer += ' Tek ölçüm yavaşlamanın kesin nedenini göstermez; disk hızı, sıcaklık ve zararlı yazılım taranmadı.'
    return answer
