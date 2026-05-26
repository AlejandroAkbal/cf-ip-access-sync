from __future__ import annotations

import ctypes
from ctypes import byref, c_char_p, c_uint32, c_void_p
import os
import platform

from .config import APP_NAME


ERR_SEC_DUPLICATE_ITEM = -25299
ERR_SEC_ITEM_NOT_FOUND = -25300


class KeychainError(RuntimeError):
    """Raised when macOS Keychain operations fail."""


def keychain_service_name(profile: str) -> str:
    return f"{APP_NAME}:{profile}"


def resolve_token(account_id: str, profile: str) -> tuple[str | None, str]:
    env_token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if env_token:
        return env_token, "env"
    token = get_token(account_id, profile)
    if token:
        return token, "keychain"
    return None, "missing"


def store_token(account_id: str, profile: str, token: str) -> None:
    if not token:
        raise KeychainError("refusing to store an empty token")
    security, corefoundation = _frameworks()
    service = keychain_service_name(profile).encode("utf-8")
    account = account_id.encode("utf-8")
    password = token.encode("utf-8")
    item = c_void_p()
    status = security.SecKeychainAddGenericPassword(
        None,
        len(service),
        c_char_p(service),
        len(account),
        c_char_p(account),
        len(password),
        c_char_p(password),
        byref(item),
    )
    try:
        if status == ERR_SEC_DUPLICATE_ITEM:
            _modify_existing_password(security, corefoundation, service, account, password)
        elif status != 0:
            raise KeychainError(f"Keychain add failed with OSStatus {status}")
    finally:
        if item.value:
            corefoundation.CFRelease(item)


def get_token(account_id: str, profile: str) -> str | None:
    security, corefoundation = _frameworks()
    service = keychain_service_name(profile).encode("utf-8")
    account = account_id.encode("utf-8")
    length = c_uint32()
    data = c_void_p()
    item = c_void_p()
    status = security.SecKeychainFindGenericPassword(
        None,
        len(service),
        c_char_p(service),
        len(account),
        c_char_p(account),
        byref(length),
        byref(data),
        byref(item),
    )
    if status == ERR_SEC_ITEM_NOT_FOUND:
        return None
    if status != 0:
        raise KeychainError(f"Keychain lookup failed with OSStatus {status}")
    try:
        raw = ctypes.string_at(data, length.value)
        return raw.decode("utf-8")
    finally:
        if data.value:
            security.SecKeychainItemFreeContent(None, data)
        if item.value:
            corefoundation.CFRelease(item)


def delete_token(account_id: str, profile: str) -> bool:
    security, corefoundation = _frameworks()
    service = keychain_service_name(profile).encode("utf-8")
    account = account_id.encode("utf-8")
    length = c_uint32()
    data = c_void_p()
    item = c_void_p()
    status = security.SecKeychainFindGenericPassword(
        None,
        len(service),
        c_char_p(service),
        len(account),
        c_char_p(account),
        byref(length),
        byref(data),
        byref(item),
    )
    if status == ERR_SEC_ITEM_NOT_FOUND:
        return False
    if status != 0:
        raise KeychainError(f"Keychain lookup failed with OSStatus {status}")
    try:
        delete_status = security.SecKeychainItemDelete(item)
        if delete_status != 0:
            raise KeychainError(f"Keychain delete failed with OSStatus {delete_status}")
        return True
    finally:
        if data.value:
            security.SecKeychainItemFreeContent(None, data)
        if item.value:
            corefoundation.CFRelease(item)


def _modify_existing_password(security: ctypes.CDLL, corefoundation: ctypes.CDLL, service: bytes, account: bytes, password: bytes) -> None:
    length = c_uint32()
    data = c_void_p()
    item = c_void_p()
    status = security.SecKeychainFindGenericPassword(
        None,
        len(service),
        c_char_p(service),
        len(account),
        c_char_p(account),
        byref(length),
        byref(data),
        byref(item),
    )
    if status != 0:
        raise KeychainError(f"Keychain lookup failed with OSStatus {status}")
    try:
        modify_status = security.SecKeychainItemModifyAttributesAndData(item, None, len(password), c_char_p(password))
        if modify_status != 0:
            raise KeychainError(f"Keychain update failed with OSStatus {modify_status}")
    finally:
        if data.value:
            security.SecKeychainItemFreeContent(None, data)
        if item.value:
            corefoundation.CFRelease(item)


def _frameworks() -> tuple[ctypes.CDLL, ctypes.CDLL]:
    if platform.system() != "Darwin":
        raise KeychainError("macOS Keychain is only available on macOS")
    security = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/Security.framework/Security")
    corefoundation = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    security.SecKeychainAddGenericPassword.argtypes = [
        c_void_p,
        c_uint32,
        c_char_p,
        c_uint32,
        c_char_p,
        c_uint32,
        c_char_p,
        ctypes.POINTER(c_void_p),
    ]
    security.SecKeychainAddGenericPassword.restype = ctypes.c_int32
    security.SecKeychainFindGenericPassword.argtypes = [
        c_void_p,
        c_uint32,
        c_char_p,
        c_uint32,
        c_char_p,
        ctypes.POINTER(c_uint32),
        ctypes.POINTER(c_void_p),
        ctypes.POINTER(c_void_p),
    ]
    security.SecKeychainFindGenericPassword.restype = ctypes.c_int32
    security.SecKeychainItemModifyAttributesAndData.argtypes = [c_void_p, c_void_p, c_uint32, c_char_p]
    security.SecKeychainItemModifyAttributesAndData.restype = ctypes.c_int32
    security.SecKeychainItemFreeContent.argtypes = [c_void_p, c_void_p]
    security.SecKeychainItemFreeContent.restype = ctypes.c_int32
    security.SecKeychainItemDelete.argtypes = [c_void_p]
    security.SecKeychainItemDelete.restype = ctypes.c_int32
    corefoundation.CFRelease.argtypes = [c_void_p]
    corefoundation.CFRelease.restype = None
    return security, corefoundation
