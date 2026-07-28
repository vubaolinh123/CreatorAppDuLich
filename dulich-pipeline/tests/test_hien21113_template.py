import generate_hien21113 as template
from tools.venue_picker import VenuePicker


def test_album_has_seven_images_and_only_slide_02_is_hotel():
    for seed in range(1, 21):
        venues = template._select_venues(VenuePicker(seed=seed))
        hotel_indexes = [
            index
            for index, venue in enumerate(venues)
            if venue.get("loai_quan") == template.HOTEL_CATEGORY
        ]

        assert len(venues) == 7
        assert hotel_indexes == [template.HOTEL_SLIDE_NUMBER]


def test_slide_02_prioritizes_seeding_hotels():
    for seed in range(1, 21):
        hotel = template._select_venues(VenuePicker(seed=seed))[2]

        assert hotel["loai_quan"] == template.HOTEL_CATEGORY
        assert hotel["loai"] == "cần seeding"


def test_slide_02_hotel_changes_between_seeds():
    hotel_names = {
        template._select_venues(VenuePicker(seed=seed))[2]["name"]
        for seed in range(1, 31)
    }

    assert len(hotel_names) > 1
