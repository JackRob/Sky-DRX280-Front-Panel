"""Execute the disassembled TWI handler with emulated AVR registers and I/O.

This is a narrow static-analysis harness, not a hardware or timing simulator.
Only the instruction subset used in this handler is implemented; unknowns fail.
"""
import re
from pathlib import Path

instructions = {}
for line in Path('work/firmware_disassembly.txt').read_text().splitlines():
    m = re.match(r'\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*([a-z]+)\s*(.*)', line)
    if m:
        address, raw, op, tail = m.groups()
        arg = tail.split(';')[0].strip()
        target = re.search(r';\s+0x([0-9a-f]+)', tail)
        instructions[int(address,16)] = (len(raw.split()),op,arg,int(target[1],16) if target else None)

class AVR:
    def __init__(self):
        self.r = [0]*32
        self.m = bytearray(0x500)
        self.c = False
        self.z = True
        self.out = []
        self.pops = 0
        self.m[0x106] = 1
        self.m[0xdf] = 0x41
        self.m[0xde] = 1
        for i in range(65): self.m[0x107+i] = (i+0x80)&255
        self.m[0x12c] = 0

    def run(self,start):
        pc=start
        stack=[]
        count=0
        while True:
            count+=1
            assert count<1000,(hex(pc),'nontermination')
            size,op,arg,target=instructions[pc]
            nextpc=pc+size
            a=[v.strip() for v in arg.split(',')]
            reg=lambda x:int(x[1:])
            imm=lambda x:int(x,0)
            if op=='ldi': self.r[reg(a[0])]=imm(a[1])
            elif op=='mov': self.r[reg(a[0])]=self.r[reg(a[1])]
            elif op=='lds': self.r[reg(a[0])]=self.m[imm(a[1])]
            elif op=='sts': self.m[imm(a[0])]=self.r[reg(a[1])]
            elif op=='in': self.r[reg(a[0])]=self.m[0x20+imm(a[1])]
            elif op=='out':
                self.m[0x20+imm(a[0])]=self.r[reg(a[1])]
                if imm(a[0])==3:self.out.append(self.r[reg(a[1])])
            elif op in ('eor','and','or','andi','ori'):
                d=reg(a[0]);v=imm(a[1]) if op.endswith('i') else self.r[reg(a[1])]
                self.r[d]=self.r[d]^v if op=='eor' else self.r[d]&v if op.startswith('and') else self.r[d]|v
                self.z=self.r[d]==0
            elif op in ('cp','cpi','subi','add','adc'):
                d=reg(a[0]);v=imm(a[1]) if op in ('cpi','subi') else self.r[reg(a[1])]
                result=self.r[d]-v if op in ('cp','cpi','subi') else self.r[d]+v+(self.c if op=='adc' else 0)
                self.c=result<0 if op in ('cp','cpi','subi') else result>255
                self.z=(result&255)==0
                if op not in ('cp','cpi'):self.r[d]=result&255
            elif op=='ld':
                assert a[1]=='Z'
                self.r[reg(a[0])]=self.m[self.r[30]+256*self.r[31]]
            elif op=='st':
                assert a[0]=='Z'
                self.m[self.r[30]+256*self.r[31]]=self.r[reg(a[1])]
            elif op in ('breq','brne','brcc','brcs'):
                take={'breq':self.z,'brne':not self.z,'brcc':not self.c,'brcs':self.c}[op]
                if take:nextpc=target
            elif op in ('rjmp','jmp'):nextpc=target
            elif op in ('rcall','call'):
                if target==0xb0a:
                    self.pops+=1; self.m[0x67]-=1
                    self.m[0x100]=0x53;self.m[0x101]=0xa6
                else:stack.append(nextpc);nextpc=target
            elif op=='ret':
                if not stack:return
                nextpc=stack.pop()
            elif op in ('cli','sei'):pass
            else:raise AssertionError((hex(pc),op,arg))
            pc=nextpc

    def event(self,status,data=0):
        self.m[0x21]=status;self.m[0x23]=data
        self.run(0x23e)

    def pointer(self,index):
        self.event(0x60);self.event(0x80,index);self.event(0xa0)

    def read(self,index,n):
        self.pointer(index);start=len(self.out)
        self.event(0xa8)
        for _ in range(n-1):self.event(0xb8)
        self.event(0xc0)
        return self.out[start:]

    def write(self,index,data):
        self.event(0x60);self.event(0x80,index)
        for value in data:self.event(0x80,value)
        self.event(0xa0)

def main():
    # A repeated START presents SLA+R while the firmware is still in its
    # receive-data state.  That state is rejected and TWI is reset/disabled.
    bad=AVR();bad.event(0x60);bad.event(0x80,1);bad.event(0xa8)
    assert bad.m[0x106]==0
    a=AVR()
    assert a.read(1,3)==[0x81,0x82,0x83]
    assert a.m[0xdf]==4
    a.write(0x10,[0x12,0x34]);assert a.read(0x10,2)==[0x12,0x34]
    a.write(1,[0x55]);assert a.read(1,1)==[0x55], 'no read-only protection in transport'
    a.write(0x40,[0x66,0x77]);assert a.read(0x40,3)==[0x66,0x80,0x80]
    a.write(0xff,[0x22]);assert a.read(0xff,2)==[0x80,0x80]
    a=AVR();a.m[0x67]=2
    for _ in range(8):a.read(0x2e,2)
    assert a.pops==0
    for i in range(5):
        a.read(0x30,2);assert a.pops==0;assert a.m[0x65]==i+1
    a.read(0x30,2);assert a.pops==1 and a.m[0x12c]&1
    assert a.read(0x2e,2)==[0x53,0xa6]
    a.read(0x31,1);assert a.pops==2 and a.m[0x65]==5
    a.read(0x31,1);assert a.pops==2 and a.m[0x12c]&1
    print('PASS: 8 groups: repeated-START rejection; STOP-separated framing; read/write increment; unprotected bank; upper boundary; invalid pointer; IR reads non-consuming; 0x31 first-five suppression then service on every preload.')

if __name__=='__main__':main()
