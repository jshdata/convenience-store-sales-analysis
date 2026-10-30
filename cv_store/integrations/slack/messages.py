"""Slack 링크 메시지와 더보기 버튼 구성. 외부 호출 없음."""

def format_news_links(news_links, date, store_type):
    """처음 3개 뉴스 링크만 출력하고, 더보기 버튼을 추가하는 함수"""
    if not news_links:
        return "📰 관련 뉴스가 없습니다.", None

    top_news = "\n".join(news_links[:3])  # 처음 3개를 문자열로 변환
    more_news = news_links[3:]  # 나머지 뉴스 링크는 더보기 버튼을 통해 출력

    message = f"📰 관련 뉴스:\n{top_news}"
    
    # 더보기 버튼 추가
    attachments = None
    if more_news:
        attachments = [
            {
                "blocks": [
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "뉴스 더보기"},
                                "action_id": "show_more_news",
                                "value": f"{date}|{store_type}"
                            }
                        ]
                    }
                ]
            }
        ]
    return message, attachments

def format_ytb_links(ytb_links, date, store_type):
    """처음 3개 유튜브 링크만 출력하고, 더보기 버튼을 추가하는 함수"""
    if not ytb_links:
        return "🎬 관련 유튜브 영상이 없습니다.", None

    top_ytb = ytb_links[:3]  # 처음 3개만 출력
    more_ytb = ytb_links[3:]  # 나머지 유튜브 링크는 더보기 버튼을 통해 출력

    message = "🎬 관련 유튜브 영상:\n" + "\n".join(top_ytb)
    
    # 더보기 버튼 추가
    attachments = None
    if more_ytb:
        attachments = [
            {
                "blocks": [
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "유튜브 더보기"},
                                "action_id": "show_more_ytb",
                                "value": f"{date}|{store_type}"
                            }
                        ]
                    }
                ]
            }
        ]
    return message, attachments
