# vocea-sdk

Official Vocea SDK for Python 3.10+.

## Installation

```bash
pip install vocea-sdk
```

## Quick Start

```python
from vocea_sdk import VoceaClient, studio_params

client = VoceaClient(api_key="vca_your_api_key")

# Generate speech
audio = client.audios.generate(
    voice_id="uuid-of-voice",
    text="Hello, world!",
    language_code="en",
    speed=1.0,
    advanced_params=studio_params(stability=50, clarity=80),
)
print(audio.audioUrl)

# Download audio bytes
data = client.audios.download(audio.id)
with open("output.mp3", "wb") as f:
    f.write(data)

# Transcribe audio
with open("recording.mp3", "rb") as f:
    result = client.stt.transcribe(f, language="en-US")
print(result.transcript)

# Clone a voice. provider_ids is required: at least one provider, and you
# can pass several to get the voice in more than one quality tier.
with open("sample.mp3", "rb") as f:
    voice = client.voices.clone(
        name="My Voice",
        audio_samples=[("sample.mp3", f, "audio/mpeg")],
        provider_ids=["provider-uuid"],
    )
print(voice.id, voice.status, voice.balanceEarnedTotal)
```

## Voices

A `Voice` carries everything the API returns for it, including its state on
each TTS provider:

```python
voice = client.voices.get("uuid-of-voice")
print(voice.gender, voice.languageCode, voice.cloneAudioDuration)
for provider in voice.providers:
    # snake_case, because that is how the API sends this one object
    print(provider.name, provider.is_cloned, provider.has_sample_preview)
```

`isFavorited` and `favoritesCount` are `None` when the endpoint does not
report them — only the listings do — and `country`/`region` are `None` unless
the query loaded them. `warnings` is only populated by `voices.clone()`.

Models ignore any key the API sends that they do not declare, so a new field
on the server never breaks an installed client.

## Balance

Balance is denominated in US dollars and every decimal field arrives as a
number, never as a string:

```python
# Current balance of the authenticated user
wallet = client.users.balance()
print(wallet.balance)  # 10.42544375

# Top-up packages, and the checkout URL to pay for one
for pkg in client.balance.list_packages():
    print(pkg.id, pkg.name, pkg.priceUsd)

checkout = client.balance.checkout(
    package_id="uuid-of-package",
    success_url="https://my-app/thanks",  # optional
)
print(checkout.checkoutUrl)

# Transaction history, optionally filtered by type
page = client.balance.list_transactions(page=1, limit=20, type="consumption")
for tx in page.items:
    # amount is positive when it adds balance, negative when it spends it
    print(tx.createdAt, tx.type, tx.amount, tx.description)
```

| Field | Model |
| --- | --- |
| `balance` | `UsdBalance` |
| `priceUsd` | `BalancePackage` |
| `amount` | `BalanceTransaction` |
| `balanceEarnedTotal` | `Voice`, `VoiceEarnings` |
| `balanceEarned` | `MonthlyEarning` |
| `balanceConsumed` | `TranscribeResult` |

## Getting an API key

Everything except `client.auth` needs an API key. If you do not have one yet,
the SDK can issue it: sign in and create one. Build the client with an empty key
when you are only going to call `auth`.

```python
from vocea_sdk import VoceaClient

session = VoceaClient(api_key="").auth.login("you@example.com", "your-password")
print(session.user.email, session.user.balance)

# The key is readable exactly once: only its hash is stored. Creating a new one
# replaces the previous key.
client = VoceaClient(api_key=session.access_token)
print(client.users.create_api_key().apiKey)
```

`auth` also covers `register`, `verify_email`, `resend_verification`,
`forgot_password`, `reset_password` and `logout`. `forgot_password` answers the
same whether or not the address exists — telling them apart would let anyone
check which emails are registered.

## Advanced generation parameters

Each quality tier takes its own parameters, and sending one from another tier
fails the call with `INVALID_ADVANCED_PARAMS`. Build the dict with the helpers:

| Tier                  | Helper                       | Parameters and ranges                                     |
| --------------------- | ---------------------------- | --------------------------------------------------------- |
| `standard` (Inworld)  | `standard_params(e)`         | `expressiveness` 0–100 (default 50)                       |
| `premium` (Minimax)   | `premium_params(p, v, emo)`  | `pitch` **integer −12…12**, `volume` 0–100, `emotion`     |
| `studio` (ElevenLabs) | `studio_params(s, c, st)`    | `stability` 0–100, `clarity` 0–100, `style` 0–100         |

Everything is a 0–100 scale that the API rescales per provider, with one
exception: `pitch` is a real semitone count, so it runs from −12 to 12 and has
to be a whole number. The helpers validate the range before the request goes
out, so a mistake costs nothing.

`speed` (0.5–1.5) applies to every tier and goes outside `advanced_params`.

## Models and providers

`models.list()` is where provider IDs come from — the ones `voices.clone()`
requires. The detail endpoint does not send them, so only the listing has them.

```python
for m in client.models.list():
    print(m.id, m.name, m.providerId, m.maxCharacters)
```

## Publishing a voice

A voice needs its origin and age range filled in before it can be submitted to
the public catalogue. Once published it earns balance every time somebody else
generates audio with it.

```python
client.voices.update_metadata(
    voice.id,
    country_id="country-uuid",
    age_range="adult",
    new_region_name="Andalucía",  # created if it does not exist yet
)

# Fails with VOICE_METADATA_INCOMPLETE if anything above is missing.
client.voices.request_public(voice.id)

earnings = client.voices.earnings(voice.id)
print(earnings.balanceEarnedTotal, earnings.timesUsed)
```

## Transcriptions

Transcriptions are stored and can be listed or removed later. Deleting one does
not refund the balance it spent.

```python
page = client.stt.list_transcriptions(page=1, limit=20)
for t in page.items:
    print(t.createdAt, t.durationMs, t.transcript)

client.stt.delete_transcription(page.items[0].id)
```

## Referrals

What each person you brought in has generated. `latestStatus` is `None` while a
referee has not purchased anything yet.

```python
stats = client.balance.referrals()
print(stats.totalEarned, stats.referralPercentage)
for r in stats.items:
    print(r.refereeEmail, r.totalUsd, r.hasPurchased)

history = client.balance.referral_history(stats.items[0].refereeId)
for c in history.transactions:
    print(c.date, c.commissionUsd, c.status)
```

## Your account

```python
me = client.users.me()
print(me.email, me.preferredLanguage, me.balance)

# The request body is snake_case and the response comes back camelCase.
# Fields you leave out are not sent, so this only changes the name.
me = client.users.update(full_name="New Name")

print(client.users.api_key_status().hasApiKey)
```

## Error Handling

```python
from vocea_sdk import VoceaError

try:
    audio = client.audios.generate(...)
except VoceaError as e:
    print(e.status_code, e.body)
    # 402 with body["errorCode"] == "INSUFFICIENT_BALANCE" means no funds left
```

## Development

```bash
pip install -e ".[dev]"
pytest -q
```

## New in 0.4.0

The SDK covered 24 of the 42 methods the API exposes. Two of those gaps left it
without a way out:

- There was no `auth` resource at all, so there was no way into the platform
  from Python — no sign-up, no sign-in.
- `users` had only `balance()`. In particular `create_api_key()` was missing,
  so the SDK required an API key and offered no way to obtain one.

`models.list()` also dropped `providerId` while deserializing. Since
`voices.clone()` requires `provider_ids` and that listing is the only place the
SDK can get them from, cloning a voice was impossible without knowing the ids
from somewhere else. It now returns `TtsModelListItem`, with `providerId` and
`maxCharacters`.

Added along the way: `stt.list_transcriptions` and `delete_transcription`,
`voices.update_metadata` and `earnings`, `audios.play_url`,
`generate(provider_voice_id=...)`, and `balance.referrals` /
`referral_history`, which no SDK covered.

`VoceaError` now exposes `error_code`. The API sanitizes its errors and often
sends no `message`, so branching on the message text never worked well; the
code is the stable part.

`advanced_params` gained the `standard_params`, `premium_params` and
`studio_params` builders. The documented range for `pitch` was wrong: it is −12
to 12 **integer** semitones, not −100 to 100. That value reaches the provider
unscaled, so anything outside that range was already being rejected upstream.
The builders validate before the request goes out.

Two deserialization bugs are fixed: `models.languages()` and `config()` used to
raise `TypeError` as soon as the backend added a field, because they unpacked
the response dict straight into the dataclass. They go through `from_dict` now,
like everything else.

## New in 0.3.0

`client.users` and `client.balance` are new: `users.balance()`,
`balance.list_packages()`, `balance.checkout()` and
`balance.list_transactions()` close the gap with the Node SDK.

## Breaking changes in 0.3.0

Every balance field and the package model were renamed, and `voices.clone()`
takes a new required `provider_ids` argument that the API already accepted.
See the table above for the current names.

`Voice` gained the fields the API had been sending all along
(`cloneAudioDuration`, `languageCode`, `gender`, `lastUsedAt`, `deletedAt`,
`providers`, `warnings`) and `Audio` gained `providerVoiceId` and
`generationTimeMs`. `Voice.langSet` is deprecated: the server dropped the
column and no longer sends it. `isFavorited`, `favoritesCount`, `country` and
`region` are now optional, and `Audio.voiceId` is nullable — audio generated
from a provider's catalogue voice has none.

## Fixed in 0.3.0

- **Voices and audios could not be read at all.** `Voice.from_dict` and
  `Audio(**d)` unpacked the whole response into the dataclass, so every field
  the server sent and the model did not declare raised a `TypeError`. Models
  now drop unknown keys, and the test fixtures are copies of real API
  responses instead of the subset the models happened to declare.
- **The package did not import on the versions it advertised.** `models.py`
  used PEP 695 generic syntax (`class PaginatedResponse[T]`), which requires
  Python 3.12, while the package claims 3.10+. It is written with `TypeVar`
  now, and a test parses every source file against the minimum version
  declared in `pyproject.toml`. Verified on 3.10, 3.11 and 3.12.
