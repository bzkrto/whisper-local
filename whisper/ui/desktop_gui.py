"""Voice and text diagnostics; Tk widgets are touched only on the UI thread."""
import queue
import sys
import threading

class QueueStream:
    def __init__(self, events, original):
        self.events, self.original = events, original
    def write(self, text):
        if text:
            self.events.put(('log', text))
        if self.original is not None:
            self.original.write(text)
        return len(text)
    def flush(self):
        if self.original is not None:
            self.original.flush()
    def isatty(self):
        return False
    @property
    def encoding(self):
        return getattr(self.original, 'encoding', 'utf-8')

def run_gui(brain):
    import tkinter as tk
    from tkinter import ttk
    from tkinter.scrolledtext import ScrolledText
    root = tk.Tk()
    root.title('WHISPER — Sohbet')
    root.geometry('950x700')
    root.minsize(650,450)
    tabs=ttk.Notebook(root)
    tabs.pack(fill='both',expand=True,padx=12,pady=12)
    conversation=tk.Frame(tabs); diagnostics=tk.Frame(tabs)
    tabs.add(conversation,text='Sohbet'); tabs.add(diagnostics,text='İşlem günlüğü')
    chat=ScrolledText(conversation,wrap='word',state='disabled',font=('Segoe UI',12),padx=14,pady=14)
    chat.pack(fill='both',expand=True)
    chat.tag_configure('user',foreground='#2459a6',spacing1=12,spacing3=12)
    chat.tag_configure('assistant',foreground='#17643d',spacing1=12,spacing3=12)
    output = ScrolledText(diagnostics, wrap='word', state='disabled', font=('Segoe UI',11))
    output.pack(fill='both', expand=True)
    status = tk.StringVar(value='Hazır · Yazılı komut için Whisper demen gerekmez')
    tk.Label(root,textvariable=status,anchor='w').pack(fill='x',padx=12)
    voice_status = tk.StringVar(value='Mikrofon kapalı')
    controls = tk.Frame(root)
    controls.pack(fill='x',padx=12)
    tk.Label(controls,textvariable=voice_status,anchor='w').pack(side='left')
    row = tk.Frame(root)
    row.pack(fill='x',padx=12,pady=12)
    entry = tk.Entry(row,font=('Segoe UI',12))
    entry.pack(side='left',fill='x',expand=True)
    events = queue.Queue()
    previous_observer=getattr(brain,'conversation_observer',None)
    brain.conversation_observer=lambda role,text:events.put(('conversation',(role,text)))
    closing = threading.Event()
    voice_stop = threading.Event()
    voice_thread = None
    busy = False
    def append(text):
        output.configure(state='normal')
        output.insert('end',text)
        output.see('end')
        output.configure(state='disabled')
    def send(event=None, text_override=None):
        nonlocal busy
        text=(text_override if text_override is not None else entry.get()).strip()
        if not text or busy:
            return
        if text_override is None:
            entry.delete(0,'end')
        append('\n⌨️ Yazılan komut: '+text+'\n')
        busy=True
        button.configure(state='disabled')
        status.set('Komut işleniyor…')
        def work():
            try:
                events.put(('result',brain.process_command(text)))
            except Exception as exc:
                events.put(('conversation',('assistant',f'Komut işleme hatası: {type(exc).__name__}: {exc}')))
                events.put(('result',{'response':f'Komut işleme hatası: {type(exc).__name__}: {exc}', 'status':'error'}))
        threading.Thread(target=work,daemon=True).start()
    def pick_pdf():
        if busy:return
        from tkinter import filedialog
        path=filedialog.askopenfilename(parent=root,title='Hafızaya aktarılacak PDF',filetypes=[('PDF dosyası','*.pdf')])
        if path:send(text_override='PDF öğren: '+path)
    tk.Button(row,text='PDF seç',command=pick_pdf).pack(side='right',padx=(8,0))
    button=tk.Button(row,text='Gönder',command=send)
    button.pack(side='right',padx=(8,0))
    entry.bind('<Return>',send)
    def toggle_voice():
        nonlocal voice_thread
        if voice_thread is not None and voice_thread.is_alive():
            voice_stop.set()
            voice_status.set('Mikrofon durduruluyor…')
            voice_button.configure(state='disabled')
            return
        voice_stop.clear()
        voice_status.set('Mikrofon hazırlanıyor…')
        voice_button.configure(text='Mikrofonu durdur')
        def listen():
            try:
                brain.start_voice_loop(stop_event=voice_stop)
            except (Exception, SystemExit) as exc:
                events.put(('log',f'\n❌ Ses giriş hatası: {type(exc).__name__}: {exc}\nYazılı komutlar kullanılabilir.\n'))
            finally:
                events.put(('voice_done',None))
        voice_thread=threading.Thread(target=listen,daemon=True)
        voice_thread.start()
    voice_button=tk.Button(controls,text='Mikrofonu başlat',command=toggle_voice)
    voice_button.pack(side='right')
    def interrupt():
        result=brain.interrupt()
        append('\n⏹️ '+result['response']+'\n')
        status.set('Yanıt iptal edildi · Yeni komut için işlem iş parçacığının kapanması bekleniyor')
    tk.Button(controls,text='Yanıtı kes',command=interrupt).pack(side='right',padx=8)
    duplex = tk.BooleanVar(value=brain.cfg.barge_in_headphones)
    def set_duplex():
        brain.cfg.barge_in_headphones=duplex.get()
        append('\nKulaklıkta söz kesme '+('açık' if duplex.get() else 'kapalı')+'. Bu mod hoparlör yankı giderme içermez.\n')
    tk.Checkbutton(controls,text='Kulaklıkta söz kesme (deneysel)',variable=duplex,command=set_duplex).pack(side='right')
    def reminders():
        while not closing.wait(2):
            try:
                for message in brain.announce_reminders():
                    events.put(('log','\n'+message+'\n'))
            except Exception as exc:
                events.put(('log',f'\nHatırlatma hatası: {type(exc).__name__}\n'))
    def research():
        while not closing.wait(30):
            try:
                brain.run_due_research()
            except Exception as exc:
                events.put(('log',f'\nAraştırma zamanlayıcısı hatası: {type(exc).__name__}\n'))
    def poll():
        nonlocal busy
        for _ in range(300):
            try:
                kind, value=events.get_nowait()
            except queue.Empty:
                break
            if kind == 'log':
                append(value)
                if 'Sistemleri Aktif' in value:
                    voice_status.set('Mikrofon açık · Hey Whisper ile başla · Sonra karşılıklı konuş')
            elif kind == 'conversation':
                role,text=value
                chat.configure(state='normal')
                chat.insert('end',('Siz' if role=='user' else 'Whisper')+'\n'+text+'\n\n',role)
                chat.see('end'); chat.configure(state='disabled')
            elif kind == 'voice_done':
                voice_status.set('Mikrofon kapalı · Yazılı komut kullanılabilir')
                voice_button.configure(text='Mikrofonu başlat',state='normal')
            elif kind == 'result':
                if value.get('status') in ('error','busy'):
                    append('\n⌨️ '+value.get('response','')+'\n')
                state=value.get('status','')
                status.set('Bir ayrıntı bekliyorum' if state=='clarification' else
                           'İşlem tamamlanamadı; ayrıntı işlem günlüğünde' if state in ('error','blocked','busy') else 'Hazır')
                busy=False
                button.configure(state='normal')
                entry.focus_set()
        if not closing.is_set():
            root.after(100,poll)
    def close():
        closing.set()
        voice_stop.set()
        brain.interrupt()
        brain.conversation_observer=previous_observer
        root.destroy()
    root.protocol('WM_DELETE_WINDOW',close)
    append('Aynı komutu önce söyle, sonra aşağıya yaz. Yazıda tetikleme kelimesi gerekmez.\n'
           'Ham metin yanlışsa ses kaydı/tanıma; doğru metinde yanlış işlem varsa komut yolu;\n'
           'seslendirme metni doğru ama telaffuz yanlışsa ses motoru incelenir.\n'
           'Mikrofonu durdurmak yalnızca ses girişini kapatır.\n\n')
    original_out, original_err=sys.stdout, sys.stderr
    sys.stdout=QueueStream(events,original_out)
    sys.stderr=QueueStream(events,original_err)
    try:
        threading.Thread(target=reminders,daemon=True).start()
        threading.Thread(target=research,daemon=True).start()
        entry.focus_set()
        root.after(100,poll)
        if brain.cfg.voice_loop_enabled and not getattr(brain.cfg,'_mode_text',False):
            root.after(200,toggle_voice)
        root.mainloop()
    finally:
        closing.set()
        voice_stop.set()
        brain.conversation_observer=previous_observer
        sys.stdout,sys.stderr=original_out,original_err
