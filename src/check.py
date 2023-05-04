import re
from dataclasses import dataclass
from urllib.parse import urljoin
from typing import List

import requests
from loguru import logger
from lxml import etree
from tqdm import tqdm


@dataclass
class Counsellor:
    per_id: str
    name: str
    title: str
    img_url: str


@dataclass
class Week:
    week_id: str
    name: str


@dataclass
class Location:
    loc_id: str
    name: str


@dataclass
class AppointmentStatusRecord:
    counsellor: Counsellor
    week: Week
    location: Location
    start_time: str
    end_time: str
    status: str


class App:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.session = requests.Session()
        self.session.cookies.set("ASP.NET_SessionId", session_id)

        self.base_url = "http://zxyy.xlzx.suda.edu.cn"
        self.app_url = urljoin(self.base_url, "Apply.aspx")
        self.info_url = urljoin(self.base_url, "Info.aspx")
        self.info_url = urljoin(self.base_url, "Info.aspx")
        self.counsellor_list_url = self.app_url + "?action=person"

        self.stu_id, self.stu_name = self.get_user_info()
        logger.info(f"Welcome, {self.stu_name} ({self.stu_id})")

        self.counsellor_list = self.get_counsellor_list()
        logger.info(f"#Counsellor: {len(self.counsellor_list)}")
        self.week_list = self.get_week_list()
        logger.info(f"#Week: {len(self.week_list)}")
        self.location_list = self.get_location_list()
        logger.info(f"#Location: {len(self.location_list)}")

    def get_user_info(self):
        response = self.session.get(self.info_url)
        html = etree.HTML(response.text)
        # fmt: off
        stu_id = html.xpath("//*[@id='container']/div[1]/div/div[2]/div[2]/text()")[0].strip()
        stu_name = html.xpath("//*[@id='container']/div[1]/div/div[3]/div[2]/text()")[0].strip()
        # fmt: on
        return stu_id, stu_name

    def get_counsellor_list(self) -> List[Counsellor]:
        response = self.session.get(self.counsellor_list_url)
        html = etree.HTML(response.text)
        a_elems = html.xpath("//a[contains(@href, 'UserID=')]")
        table_elems = html.xpath("//table")

        counsellors = []
        for elem, table in zip(a_elems, table_elems):
            # fmt: off
            user_id = re.search(r"UserID=(\d+)", elem.xpath("@href")[0]).group(1).strip()
            img_url = urljoin(self.base_url, table.xpath(".//img/@src")[0].strip())
            # fmt: on
            name = table.xpath(".//h4/text()")[0].strip()
            title = table.xpath(".//p/text()")[0].strip()

            counsellors.append(Counsellor(user_id, name, title, img_url))

        return counsellors

    def get_week_list(self) -> List[Week]:
        response = self.session.get(self.app_url)
        html = etree.HTML(response.text)
        elems = html.xpath('//*[@id="weui_actionsheet1"]/div[1]/div')

        weeks = []
        for elem in elems:
            week_id = elem.xpath("./@rel")[0].strip()
            name = elem.xpath("./text()")[0].strip()
            weeks.append(Week(week_id, name))

        return weeks

    def get_location_list(self) -> List[Location]:
        response = self.session.get(self.app_url)
        html = etree.HTML(response.text)
        elems = html.xpath('//*[@id="weui_actionsheet2"]/div[1]/div')

        locations = []
        for elem in elems:
            loc_id = elem.xpath("./@rel")[0].strip()
            name = elem.xpath("./text()")[0].strip()
            locations.append(Location(loc_id, name))

        return locations

    def get_appointment_info(
        self, counsellor: Counsellor, week: Week, location: Location
    ) -> List[AppointmentStatusRecord]:
        url = f"http://zxyy.xlzx.suda.edu.cn/book.aspx?UserID={counsellor.per_id}&Week={week.week_id}&AreaID={location.loc_id}"
        response = self.session.get(url)

        if "没有排班" in response.text:
            return []

        html = etree.HTML(response.text)
        start_times = html.xpath("//span[@class='startTime']/text()")
        end_times = html.xpath("//span[@class='endTime']/text()")
        status_list = html.xpath("//a[contains(@class, 'bntBook')]/text()")

        records = []
        for start_time, end_time, status in zip(start_times, end_times, status_list):
            records.append(
                AppointmentStatusRecord(
                    counsellor, week, location, start_time, end_time, status
                )
            )

        return records

    def get_all_infos(self):
        if not self.counsellor_list:
            self.counsellor_list = self.get_counsellor_list()
        if not self.week_list:
            self.week_list = self.get_week_list()
        if not self.location_list:
            self.location_list = self.get_location_list()

        infos = self.get_infos(self.counsellor_list, self.week_list, self.location_list)

        return infos

    def get_infos(self, counsellor_list: List[Counsellor], week_list: List[Week], location_list: List[Location]) -> List[AppointmentStatusRecord]:
        infos = []
        for c in tqdm(counsellor_list):
            for week in week_list:
                for loc in location_list:
                    info_list = self.get_appointment_info(c, week, loc)
                    infos.extend(info_list)

        return infos

    def get_appointment_url(self, record: AppointmentStatusRecord):
        url = f"http://zxyy.xlzx.suda.edu.cn/book.aspx?UserID={record.counsellor.per_id}&Week={record.week.week_id}&AreaID={record.location.loc_id}"
        return url


if __name__ == "__main__":
    app = App("ASP.NET_SessionId")

    counsellors = app.counsellor_list
    weeks = app.week_list
    locations = list(filter(lambda x: "彩虹楼" in x.name, app.location_list))

    infos = app.get_infos(counsellors, weeks, locations)
    logger.info(f"#infos: {len(infos)}")
    available_infos = list(filter(lambda info: info.status != "已约", infos))
    logger.info(f"#available infos: {len(available_infos)}")

    for info in available_infos:
        logger.info(f"{info}")
        logger.info(f"url: {app.get_appointment_url(info)}")
