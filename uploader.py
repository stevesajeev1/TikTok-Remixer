# See https://github.com/546200350/TikTokUploder

import requests
import json
import time
import datetime
from x_bogus_ import get_x_bogus
from urllib.parse import urlencode

from util import assertSuccess, printError, getTagsExtra, uploadToTikTok, log, getCreationId


UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36'


def uploadVideo(session_id, video, title, tags, users=[], url_prefix="us", schedule_time: int = 0, proxy: dict = None):
	if schedule_time - datetime.datetime.now().timestamp() > 864000:  # 864000s = 10 days
		print("[-] Can not schedule video in more than 10 days")
		return False

	session = requests.Session()

	if proxy:
		session.proxies.update(proxy)
	session.cookies.set("sessionid", session_id, domain=".tiktok.com")
	session.verify = True
	headers = {
		'User-Agent': UA
	}
	url = f"https://{url_prefix}.tiktok.com/upload/"
	r = session.get(url, headers=headers)
	if not assertSuccess(url, r):
		return False
	creationid = getCreationId()
	url = f"https://{url_prefix}.tiktok.com/api/v1/web/project/create/?creation_id={creationid}&type=1&aid=1988"
	headers = {
		"X-Secsdk-Csrf-Request": "1",
		"X-Secsdk-Csrf-Version": "1.2.8"
	}
	r = session.post(url, headers=headers)
	if not assertSuccess(url, r):
		return False
	try:
		tempInfo = r.json()['project']
	except KeyError:
		print(f"[-] An error occured while reaching {url}")
		print("[-] Please try to change the --url_server argument to the adapted prefix for your account")
		return False
	creationID = tempInfo["creationID"]
	projectID = tempInfo["project_id"]
	# 获取账号信息
	url = f"https://{url_prefix}.tiktok.com/passport/web/account/info/"
	r = session.get(url)
	if not assertSuccess(url, r):
		return False
	# user_id = r.json()["data"]["user_id_str"]
	log("Start uploading video")
	video_id = uploadToTikTok(video, session)
	if not video_id:
		log("Video upload failed")
		return False
	log("Video uploaded successfully")
	time.sleep(2)
	result = getTagsExtra(title, tags, users, session, url_prefix)
	time.sleep(3)
	title = result[0]
	text_extra = result[1]
	postQuery = {
		'app_name': 'tiktok_web',
		'channel': 'tiktok_web',
		'device_platform': 'web',
		'aid': 1988
	}
	data = {
		"upload_param": {
			"video_param": {
				"text": title,
				"text_extra": text_extra,
				"poster_delay": 0
			},
			"visibility_type": 0,
			"allow_comment": 1,
			"allow_duet": 0,
			"allow_stitch": 0,
			"sound_exemption": 0,
			"geofencing_regions": [],
			"creation_id": creationID,
			"is_uploaded_in_batch": False,
			"is_enable_playlist": False,
			"is_added_to_playlist": False
		},
		"project_id": projectID,
		"draft": "",
		"single_upload_param": [],
		"video_id": video_id,
		"creation_id": creationID
	}
	if schedule_time and schedule_time - datetime.datetime.now().timestamp() > 900:  # 900s = 15min
		data["upload_param"]["schedule_time"] = schedule_time
	postQuery['X-Bogus'] = get_x_bogus(urlencode(postQuery), json.dumps(data, separators=(',', ':')), UA)
	url = 'https://us.tiktok.com/api/v1/web/project/post/'
	headers = {
		'Host': f'{url_prefix}.tiktok.com',
		'content-type': 'application/json',
		'user-agent': UA,
		'origin': 'https://www.tiktok.com',
		'referer': 'https://www.tiktok.com/'
	}
	r = session.post(url, params=postQuery, data=json.dumps(data, separators=(',', ':')), headers=headers)
	if not assertSuccess(url, r):
		log("Publish failed")
		printError(url, r)
		return False
	if r.json()["status_code"] == 0:
		log(f"Published successfully {'| Scheduled for ' + str(schedule_time) if schedule_time else ''}")
	else:
		log("Publish failed")
		printError(url, r)
		return False

	return True