#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ma'lumotlar bazasi bilan ishlash
"""

import json
import os
from config import DATA_FILE


def load_data():
    """Ma'lumotlarni yuklash"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Eski ma'lumotlar bazasida 'users' bo'lmasligi mumkin
            if 'users' not in data:
                data['users'] = {}
            return data
    return {
        "admins": [],
        "mandatory_channels": [],
        "tests": {},
        "user_results": {},
        "users": {}
    }


def save_data(data):
    """Ma'lumotlarni saqlash"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

