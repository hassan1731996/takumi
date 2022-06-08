INFORMATION_MAPPING = {
    "type": "nested",
    "properties": {
        "id": {"type": "keyword"},
        "account_type": {"type": "keyword"},
        "hair_colour.id": {"type": "keyword"},
        "hair_colour.category": {"type": "keyword"},
        "eye_colour.id": {"type": "keyword"},
        "hair_type.id": {"type": "keyword"},
        "glasses": {"type": "boolean"},
        "languages": {"type": "keyword"},
        "tags.id": {"type": "keyword"},
        "children": {
            "type": "nested",
            "properties": {
                "id": {"type": "keyword"},
                "gender": {"type": "keyword"},
                "birthday": {"type": "date", "format": "yyyy-MM-dd"},
                "born": {"type": "boolean"},
            },
        },
    },
}
