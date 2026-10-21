"""AURA's charcoal/teal design primitives, drawn locally without font icons."""
import tkinter as tk

BG = '#0C1219'
PANEL = '#141D27'
SIDEBAR = '#111B25'
LINE = '#2C3B49'
TEXT = '#F0F4FA'
MUTED = '#A9BACB'
TEAL = '#31D0C3'
SELECT = '#16363E'
RED = '#F17A85'


def rounded(canvas, x1, y1, x2, y2, radius=10, **kwargs):
    r = min(radius, (x2-x1)/2, (y2-y1)/2)
    return canvas.create_polygon(x1+r,y1, x2-r,y1, x2,y1, x2,y1+r,
        x2,y2-r, x2,y2, x2-r,y2, x1+r,y2, x1,y2, x1,y2-r, x1,y1+r, x1,y1,
        smooth=True, splinesteps=24, **kwargs)


def icon(c, kind, x, y, size=24, color=MUTED):
    """Stroke icons in a normalized 24-unit coordinate system."""
    s = size/24
    def line(*points):
        return c.create_line(*[v*s+(x if i%2==0 else y) for i,v in enumerate(points)], fill=color, width=1.6*s, capstyle='round', joinstyle='round')
    def box(a,b,d,e):
        c.create_rectangle(x+a*s,y+b*s,x+d*s,y+e*s,outline=color,width=1.5*s)
    def oval(a,b,d,e):
        c.create_oval(x+a*s,y+b*s,x+d*s,y+e*s,outline=color,width=1.5*s)
    if kind == 'home':
        line(2,11,12,2,22,11); line(5,9,5,22,10,22,10,15,15,15,15,22,20,22,20,9)
    elif kind == 'processes':
        for j in (5,12,19):
            oval(2,j-1,4,j+1); line(8,j,22,j)
    elif kind == 'power':
        line(14,1,4,14,11,14,9,23,21,9,13,9,14,1)
    elif kind == 'calendar':
        box(3,5,21,22); line(3,10,21,10); line(8,2,8,7); line(16,2,16,7)
    elif kind == 'connection':
        oval(10,10,14,14)
        for a,b,d,e in ((6,6,18,18),(2,2,22,22)):
            c.create_arc(x+a*s,y+b*s,x+d*s,y+e*s,start=135,extent=90,style='arc',outline=color,width=1.5*s)
            c.create_arc(x+a*s,y+b*s,x+d*s,y+e*s,start=-45,extent=90,style='arc',outline=color,width=1.5*s)
    elif kind == 'cpu':
        box(5,5,19,19); box(9,9,15,15)
        for v in (8,12,16):
            line(v,1,v,4); line(v,20,v,23); line(1,v,4,v); line(20,v,23,v)
    elif kind == 'ram':
        box(2,5,22,18)
        for v in (6,11,16):
            box(v,8,v+2,13); line(v,18,v,22)
        line(2,22,22,22)
    elif kind == 'search':
        oval(2,2,17,17); line(15,15,22,22)
    elif kind == 'trash':
        line(3,6,21,6); box(6,6,18,22); line(9,6,9,2,15,2,15,6); line(10,10,10,18); line(14,10,14,18)
    elif kind == 'refresh':
        c.create_arc(x+3*s,y+3*s,x+21*s,y+21*s,start=40,extent=285,style='arc',outline=color,width=1.6*s)
        line(21,2,21,8,15,8)
    elif kind == 'history':
        oval(2,2,22,22); line(12,6,12,12,17,15)
    else:
        box(3,3,21,21); line(8,8,16,8); line(8,12,16,12); line(8,16,13,16)


class Button(tk.Canvas):
    def __init__(self, parent, text, command, kind=None, accent=False, danger=False, nav=False, **kw):
        super().__init__(parent, height=48, bg=parent.cget('bg'), highlightthickness=0,
                         takefocus=True, cursor='hand2', **kw)
        self.text, self.command, self.kind = text, command, kind
        self.accent, self.danger, self.nav = accent, danger, nav
        self.active, self.hover, self.enabled = False, False, True
        self.bind('<Configure>', self.draw)
        self.bind('<Enter>', lambda _: self.set_hover(True))
        self.bind('<Leave>', lambda _: self.set_hover(False))
        self.bind('<Button-1>', self.invoke)
        self.bind('<Return>', self.invoke)
        self.bind('<space>', self.invoke)
        self.bind('<FocusIn>', self.draw); self.bind('<FocusOut>', self.draw)

    def invoke(self, _=None):
        if self.enabled:
            self.focus_set(); self.command()

    def set_hover(self, value):
        self.hover = value; self.draw()

    def set_enabled(self, value):
        self.enabled = value; self.configure(cursor='hand2' if value else 'arrow'); self.draw()

    def draw(self, _=None):
        self.delete('all'); w, h = self.winfo_width(), self.winfo_height()
        color = TEAL if self.accent else RED if self.danger else TEXT
        fill = '#23414A' if self.hover else SELECT if self.active else '#38232D' if self.danger else PANEL
        if self.nav and not self.active and not self.hover:
            fill = self.cget('bg'); color = MUTED
        if not self.enabled:
            color = '#647686'
        border = TEAL if self.focus_get() == self else '#78404B' if self.danger else LINE
        rounded(self, 1,1,w-1,h-1,8,fill=fill,outline=border if not self.nav or self.active else fill)
        if self.active and self.nav:
            self.create_line(2,8,2,h-8,fill=TEAL,width=3)
            color = TEAL
        tx = 18
        if self.kind:
            icon(self, self.kind, 17,(h-23)/2,23,color); tx = 55
        self.create_text(tx,h/2,text=self.text,anchor='w',fill=color,font=('Segoe UI',11,'bold' if self.active else 'normal'))


class Metric(tk.Canvas):
    def __init__(self, parent, kind):
        super().__init__(parent, height=102, bg=parent.cget('bg'), highlightthickness=0)
        self.kind = kind; self.value = None; self.used = None; self.total = None; self.samples = []
        self.bind('<Configure>', self.draw)

    def update_value(self, data):
        self.value = data[self.kind]
        self.used, self.total = data.get('ram_used_gb'), data.get('ram_total_gb')
        if self.kind == 'cpu':
            self.samples = (self.samples + [self.value])[-28:]
        self.draw()

    def draw(self, _=None):
        self.delete('all'); w = self.winfo_width()
        rounded(self,1,1,w-1,101,12,fill=PANEL,outline=LINE)
        icon(self,self.kind,22,35,30)
        self.create_text(72,25,text=self.kind.upper(),anchor='w',fill=MUTED,font=('Segoe UI',10))
        value = '—' if self.value is None else f'{self.value:g}%'
        if self.kind == 'ram' and self.used is not None:
            value = f'{self.used:g} GB'
        self.create_text(72,51,text=value,anchor='w',fill=TEXT,font=('Segoe UI',19,'bold'))
        if self.kind == 'ram':
            sub = 'Aguardando conexão' if self.total is None else f'de {self.total:g} GB'
            self.create_text(72,79,text=sub,anchor='w',fill=MUTED,font=('Segoe UI',9))
            left = max(200,w*.55); right=w-56
            if right > left:
                rounded(self,left,49,right,61,6,fill='#263340',outline='')
                if self.value:
                    rounded(self,left,49,left+(right-left)*min(100,max(0,self.value))/100,61,5,fill=TEAL,outline='')
                self.create_text(w-16,55,text='—' if self.value is None else f'{self.value:g}%',anchor='e',fill=MUTED,font=('Segoe UI',10))
        elif len(self.samples)>1 and w>230:
            left=max(160,w*.43); width=w-left-18
            points=[]
            for i,v in enumerate(self.samples):
                points.extend((left+i*width/(len(self.samples)-1),81-v*.48))
            self.create_line(*points,fill=TEAL,width=2,smooth=True)
