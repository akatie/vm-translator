from logging import getLogger, StreamHandler, Formatter, DEBUG, INFO
from sys import stdout
from abc import ABCMeta

import yara

from vm.obfuscation import get_bytes, extract_obfuscation, is_eax, is_ebx


class Mnemonic(object):
    __metaclass__ = ABCMeta

    def _set_logging(self, verbose):
        self._logger = getLogger(hex(hash(self)))
        if verbose:
            self._logger.setLevel(DEBUG)
        else:
            self._logger.setLevel(INFO)
        log_handler = StreamHandler(stdout)
        log_handler.setFormatter(Formatter('[%(levelname)s]\t%(message)s'))
        self._logger.addHandler(log_handler)

    def __init__(self, code, verbose=False):
        self.code = code
        self._set_logging(verbose)

    def __str__(self):
        try:
            return self.name
        except NameError:
            return "UNK"


class WProtectMnemonic(Mnemonic):
    def __init__(self, code):
        super(WProtectMnemonic, self).__init__(code)
        self.name = self.recognize(code)
        self.key_update = extract_obfuscation(code, is_ebx)["ebx"]
        if any(["ESI" in str(line.args[1])
                for line in code
                if line.name == "MOV"]):
            self.imm_update = extract_obfuscation(code, is_eax)["eax"]
        else:
            self.imm_update = None
        self.ip_shift = self.guess_ip_shift(code)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return get_bytes(self.code) == get_bytes(other.code)
        else:
            return False

    @staticmethod
    def guess_ip_shift(code):
        shift = []
        for line in code:
            if line.name == "MOV":
                args = str(line.args[1])
                if "ESI" in args:
                    if "@32" in args:
                        shift.append(4)
                    elif "@16" in args:
                        shift.append(2)
                    elif "@8" in args:
                        shift.append(1)
        return shift

    @staticmethod
    def recognize(code):
        ruleset = yara.compile("mnemonics.yara")
        match = ruleset.match(data="".join(get_bytes(code)))
        return [x.rule for x in match]

    @staticmethod
    def consolidate_names(mnemonics):
        decided = []
        undecided = []
        for m in mnemonics:
            if len(m.name) == 2:  # name decided
                m.name = m.name[1 - m.name.index("nop")]
                decided.append(m.name)
            elif len(m.name) == 1:  # nop
                m.name = m.name[0]
                decided.append(m.name)
            else:
                undecided.append(m)
        for m in undecided:
            m.name = [name for name in m.name if name not in decided]
            if len(m.name) == 1:
                m.name = m.name[0]
                decided.append(m.name)
            else:
                m.__logger.debug("Not consolidated: %s", str(m.name))
