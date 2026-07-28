from pathlib import Path

import generate_hien21113 as template


class _Picker:
    def __init__(self):
        self.calls = []

    def image(self, venue):
        self.calls.append(venue)
        return "random.jpg"


def _venues():
    return [
        {"name": "Cover"},
        {"name": "Venue 1"},
        {"name": "Venue 2"},
        {"name": "Anmai Boutique Hotel"},
        {"name": "Venue 4"},
    ]


def test_slide_02_is_always_pinned_without_duplicate():
    venues = template._pin_slide_02(_venues())

    assert venues[2] == template.PINNED_SLIDE_VENUE
    assert sum(
        venue["name"] == template.PINNED_SLIDE_VENUE["name"]
        for venue in venues
    ) == 1
    assert venues[3]["name"] == "Venue 2"


def test_slide_02_uses_fixed_image_and_skips_random_picker():
    picker = _Picker()

    background = template._slide_background(
        template.PINNED_SLIDE_NUMBER,
        template.PINNED_SLIDE_VENUE,
        picker,
    )

    assert Path(background).resolve() == template.PINNED_SLIDE_IMAGE.resolve()
    assert picker.calls == []


def test_other_slides_remain_random():
    picker = _Picker()
    venue = {"name": "Venue 1"}

    assert template._slide_background(1, venue, picker) == "random.jpg"
    assert picker.calls == [venue]
