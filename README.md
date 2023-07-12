# TikTok Remixer
 
Listens for a specific user to upload a new video for TikTok, and automatically downloads, remixes, and reuploads it.

The video is listened for using the package `tiktokapipy`. (See <https://github.com/Russell-Newton/TikTokPy>) Slideshows are skipped as downloading will not work for them.

During the remixing process, the video is edited by choosing a random .mp4 video from `pointing_clips` and stacking it
underneath it.

The video is then automatically uploaded to TikTok using your TikTok `session-id`, which needs to be updated every so often. (See <https://github.com/546200350/TikTokUploder>)

To get it, log into your TikTok account and once you are on the page, press the F12 key on your keyboard to open developer tools. Then, go to Application > Storage > Cookies and find the value of the sessionid cookie. You should have something like this: `7a9f3c5d8f6e4b2a1c9d8e7f6a5b4c3d`

**Note that your TikTok sessionid cookie needs to be updated every 2 months.**

Notifications of the new video and of changes to session-id/errors are logged using Discord bots/webhooks.
