"""7.3-inch six-colour (E) ONLY. Adapted from Waveshare epd7in3e, MIT.
See NOTICE.txt for the complete upstream licence and reviewed source SHA.
No GPIO libraries are imported until a real hardware update is requested.
"""
from __future__ import annotations
import logging
import time
from pathlib import Path
from .palette import pack

LOG=logging.getLogger(__name__)
INIT_SEQUENCE=(
    (0xAA,(0x49,0x55,0x20,0x08,0x09,0x18)),
    (0x01,(0x3F,)),(0x00,(0x5F,0x69)),
    (0x03,(0x00,0x54,0x00,0x44)),(0x05,(0x40,0x1F,0x1F,0x2C)),
    (0x06,(0x6F,0x1F,0x17,0x49)),(0x08,(0x6F,0x1F,0x1F,0x22)),
    (0x30,(0x03,)),(0x50,(0x3F,)),(0x60,(0x02,0x00)),
    (0x61,(0x03,0x20,0x01,0xE0)),(0x84,(0x01,)),(0xE3,(0x2F,)),
)

class DisplayError(RuntimeError): pass

class PiIO:
    def __init__(self, settings):
        self.spi=None; self.pins=[]; self.rst=self.dc=self.busy=None
        if not Path('/dev/spidev0.0').exists():
            raise DisplayError('SPI0 missing: enable SPI in sudo raspi-config, then reboot')
        try:
            import spidev
            from gpiozero import DigitalOutputDevice, DigitalInputDevice
            self.spi=spidev.SpiDev()
            self.spi.open(0,0)
            self.spi.max_speed_hz=settings.spi_speed_hz
            self.spi.mode=0
            # CE0 is driven by the SPI kernel driver. Do NOT claim GPIO8 separately.
            self.rst=DigitalOutputDevice(17,initial_value=True);self.pins.append(self.rst)
            self.dc=DigitalOutputDevice(25,initial_value=False);self.pins.append(self.dc)
            # A disconnected BUSY should read low and time out, not look instantly complete.
            self.busy=DigitalInputDevice(24,pull_up=False);self.pins.append(self.busy)
        except Exception as exc:
            self.close()
            raise DisplayError('SPI/GPIO setup failed: %s. Check packages and gpio/spi groups.' % exc) from exc

    def reset(self,value): self.rst.value=value
    def command(self,value):
        self.dc.off(); self.spi.writebytes([value])
    def data(self,values):
        self.dc.on()
        self.spi.writebytes2(bytes(values))
    def ready(self): return bool(self.busy.value)
    def close(self):
        if self.spi is not None:
            try:self.spi.close()
            except Exception:pass
        for pin in reversed(self.pins):
            try:pin.close()
            except Exception:pass
        self.pins=[]

class EPD:
    def __init__(self,settings,io=None):
        self.settings=settings;self.io=io;self.initialised=False

    def wait_idle(self):
        time.sleep(0.02)
        deadline=time.monotonic()+self.settings.busy_timeout_seconds
        while not self.io.ready():
            if time.monotonic()>=deadline:
                raise DisplayError('BUSY timed out. Check GPIO24 (physical 18), VCC/GND, '
                                   'ribbon seating and switch 0 / 4-line SPI. No rapid retry.')
            time.sleep(0.01)

    def initialise(self):
        if self.io is None:self.io=PiIO(self.settings)
        self.io.reset(1);time.sleep(.02)
        self.io.reset(0);time.sleep(.002)
        self.io.reset(1);time.sleep(.02)
        self.wait_idle();time.sleep(.03)
        for cmd,data in INIT_SEQUENCE:
            self.io.command(cmd);self.io.data(data)
        self.io.command(0x04);self.wait_idle()
        self.initialised=True

    def show(self,frame):
        buf=pack(frame,self.settings.rotation)
        if len(buf)!=192000:raise DisplayError('Wrong frame length')
        self.initialise()
        self.io.command(0x10);self.io.data(buf)
        self.io.command(0x04);self.wait_idle()
        started=time.monotonic()
        self.io.command(0x12);self.io.data([0x00]);self.wait_idle()
        elapsed=time.monotonic()-started
        self.io.command(0x02);self.io.data([0x00]);self.wait_idle()
        if elapsed<1.0:
            raise DisplayError('BUSY returned in under one second: this is not a normal full '
                               'colour refresh. Check BUSY wiring before treating it as success.')
        LOG.info('Panel full refresh completed in %.1fs',elapsed)

    def close(self):
        if self.io is None:return
        try:
            # Use the normal deep-sleep command even after an interrupted update.
            self.io.command(0x07);self.io.data([0xA5]);time.sleep(2)
        except Exception:pass
        finally:self.io.close();self.io=None


def display(frame,settings):
    epd=EPD(settings)
    try:epd.show(frame)
    finally:epd.close()
