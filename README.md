# TikTok Remixer
 
Listens for a specific user to upload a new video for TikTok, and automatically downloads, remixes, and reuploads it.

The video is listened for using the package `tiktokapipy`. (See <https://github.com/Russell-Newton/TikTokPy>) Slideshows are skipped as downloading will not work for them.

During the remixing process, the video is edited by choosing a random .mp4 video from `pointing_clips` and stacking it
underneath it.

The video is then automatically uploaded to TikTok using your TikTok `session-id`, which needs to be updated every so often. (See <https://github.com/546200350/TikTokUploder>)

Notifications of the new video and of changes to session-id/errors are logged using Discord bots/webhooks.