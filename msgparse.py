
def thread_message(thread, ai_description):
    # 构建帖子消息文本。先输出基本信息，如果存在 AI 描述则添加并在长度超过
    # 200 字时补充省略号，最后附上帖子链接。
    base_msg = (
        f"{thread['domain'].upper()} 新促销\n"
        f"标题：{thread['title']}\n"
        f"作者：{thread['creator']}\n"
        f"时间：{thread['pub_date'].strftime('%Y/%m/%d %H:%M')}\n\n"
    )
    # 处理 AI 描述部分
    if ai_description:
        desc_snippet = ai_description[:200].strip()
        if len(ai_description) > 200:
            desc_snippet += "..."
        base_msg += f"{desc_snippet}\n\n"
    base_msg += thread['link']
    return base_msg

def comment_message(thread, comment, ai_description):
    # 构建评论消息文本。
    base_msg = (
        f"{thread['domain'].upper()} 新评论\n"
        f"作者：{comment['author']}\n"
        f"时间：{comment['created_at'].strftime('%Y/%m/%d %H:%M')}\n\n"
        f"{comment['message'][:200].strip()}...\n\n"
    )
    if ai_description:
        desc_snippet = ai_description[:200].strip()
        if len(ai_description) > 200:
            desc_snippet += "..."
        base_msg += f"{desc_snippet}\n\n"
    base_msg += comment['url']
    return base_msg

