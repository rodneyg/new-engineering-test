My first decision was to immediately fork the project and then use Windsurf and Codex to help me create a plan.

When I was testing, I saw that there was a Gemini API error, so I had to create a fallback for that. Then I also needed to update the Gemini models, which included me making a simple script to see the Gemini models that my API key had access to.

My decision around the conversations and deletions was inspired by testing and they were building up. So it just made sense to have a delete button.

When I asked Codex for ideas, the one that stood out to me was the rate limiting because I just thought that that's a commonly missed one or overlooked one. And it is very important, especially when you're using API keys, and abuse can really add up very quickly.

I also made a decision to be more concrete with actionable insights. I thought that we had statistics and insights plus we could see the data, but they weren't actionable. I just wanted to make sure that they were actionable, and I thought that we can use the Gemini API to do that. So I set up a way so we could pass that data to Gemini for dynamically generated actionable insights.

Later, I noticed sometimes the comments weren't clear if they were saving and that's why I added a button to submit feedback.
