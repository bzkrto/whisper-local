"""Validated adapter for model-selected desktop actions; dispatch is not goal success."""
ACTIONS={'click','scroll','type','keys','capture','inspect'}
KEYS={'tab':('tab',),'shift_tab':('shift','tab'),'escape':('esc',),
      'next_tab':('ctrl','tab'),'address_bar':('ctrl','l'),'new_tab':('ctrl','t'),
      'copy':('ctrl','c'),'paste':('ctrl','v'),'select_all':('ctrl','a')}

def validate_desktop(args):
    if not isinstance(args,dict) or set(args)!={'action','value'} or not isinstance(args['action'],str) or args['action'] not in ACTIONS:
        raise ValueError('Masaüstü eylemi geçersiz.')
    action,value=args['action'],args['value']
    if action=='click' and (not isinstance(value,list) or len(value)!=2 or any(type(x) is not int or not 0<=x<=32000 for x in value)):
        raise ValueError('Tıklama gerçek ekranın iki tam sayı koordinatını gerektirir.')
    if action=='scroll' and (type(value) is not int or not -10<=value<=10):raise ValueError('Kaydırma -10 ile 10 arasında olmalı.')
    if action in ('type','inspect') and (not isinstance(value,str) or not 1<=len(value)<=2000 or any(ord(c)<32 for c in value)):
        raise ValueError('Tek satırlık metin gerekli.')
    if action=='keys' and (not isinstance(value,str) or value not in KEYS):raise ValueError('Tuş işlemi desteklenmiyor.')
    if action=='capture' and value is not None:raise ValueError('Ekran kaydı value:null gerektirir.')

def execute_desktop(args, controller):
    validate_desktop(args)
    action,value=args['action'],args['value']
    if action=='inspect':raise ValueError('Ekran inceleme görüntü modeli adaptöründen yapılmalı.')
    if action=='keys':value=KEYS[value]
    if action=='click':
        width,height=controller._gui().size()
        if value[0]>=width or value[1]>=height:return {'status':'error','response':'Koordinat ekranın dışında; işlem yapılmadı.'}
    answer=controller.execute(action,value)
    return {'status':'success' if action=='capture' else 'dispatched','response':answer,
            'verification':'file_saved' if action=='capture' else 'input_dispatched_not_goal_verified'}
