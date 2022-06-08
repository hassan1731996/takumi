from takumi.models.media import Image, Media, Video


def test_creating_media_from_image_dict(instagram_post):
    image_url = "http://image.jpg"
    media = Media.from_dict({"type": "image", "url": image_url}, instagram_post)

    assert isinstance(media, Image)
    assert media.url == image_url


def test_creating_media_from_video_dict(instagram_post):
    image_url = "http://image.jpg"
    video_url = "http://video.mp4"
    media = Media.from_dict(
        {"type": "video", "thumbnail": image_url, "url": video_url}, instagram_post
    )

    assert isinstance(media, Video)
    assert media.url == video_url
    assert media.thumbnail == image_url
