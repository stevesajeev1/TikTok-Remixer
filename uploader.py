# See https://github.com/546200350/TikTokUploder
# Slightly modified (mainly to remove additional logging)

import requests, json, time
import subprocess, re
from util import assertSuccess,getTagsExtra,uploadToTikTok,getCreationId
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36'

def uploadVideo(session_id, video, title, tags, users = [], url_prefix = "us"):
	session = requests.Session()

	session.cookies.set("sessionid", session_id, domain=".tiktok.com")
	session.verify = True
	headers = {
		'User-Agent': UA
	}
	url = f"https://{url_prefix}.tiktok.com/upload/"
	r = session.get(url,headers = headers)
	if not assertSuccess(url, r):
		return False
	creationid = getCreationId()
	url = f"https://{url_prefix}.tiktok.com/api/v1/web/project/create/?creation_id={creationid}&type=1&aid=1988"
	headers = {
		"X-Secsdk-Csrf-Request":"1",
		"X-Secsdk-Csrf-Version":"1.2.8"
	}
	r = session.post(url, headers=headers)
	if not assertSuccess(url, r):
		return False
	try:
		tempInfo = r.json()['project']
	except KeyError:
		print(f"[-] An error occured while reaching {url}")
		print("[-] Please try to change the --url_server argument to the adapted prefix for your account")
	creationID = tempInfo["creationID"]
	projectID = tempInfo["project_id"]
	# 获取账号信息
	url = f"https://{url_prefix}.tiktok.com/passport/web/account/info/"
	r = session.get(url)
	if not assertSuccess(url, r):
		return False
	# user_id = r.json()["data"]["user_id_str"]
	video_id = uploadToTikTok(video,session)
	if not video_id:
		return False
	time.sleep(2)
	result = getTagsExtra(title,tags,users,session,url_prefix)
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
	command = ['node', './js/webssdk.js', json.dumps(data)]

	response = subprocess.check_output(command, encoding='utf-8').strip()[2:]

	response = response.replace("'", "\"")
	response = re.sub(r"(\w+):\s", r'"\1": ', response)

	response = json.loads(response)

	url = response['url']
	ua = response['ua']

	reqData = json.dumps(data, separators=(',', ':'), ensure_ascii=False);
	headers = {
		'Host': f'{url_prefix}.tiktok.com',
		'content-type': 'application/json',
		'user-agent': ua,
		'origin': 'https://www.tiktok.com',
		'referer': 'https://www.tiktok.com/'
	}
	r = session.post(url, data=reqData.encode('utf-8'), headers=headers)
	if not assertSuccess(url, r) or r.json()["status_code"] != 0:
		return False

	return True