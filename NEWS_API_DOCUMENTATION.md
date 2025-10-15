# News API Documentation

## Base URLs

**Production:**
```
https://api.agrosearch.kz/api
```

**Demo/Staging:**
```
https://api.demo.agrosearch.kz/api
```

## Table of Contents
1. [Authentication](#authentication)
2. [Image Upload](#image-upload)
3. [Create News](#create-news-endpoint)

---

## Authentication

### Login Endpoint

To create news, you must first authenticate and obtain a JWT token.

#### Endpoint
```
POST /auth/login
```

#### Authentication
**Not required** - This is the endpoint to GET authentication.

#### Headers
```
Content-Type: application/json
Accept-Language: ru (optional, default: ru)
```

#### Request Body

You can login with either **email** OR **phone number**:

**Option 1: Login with Email**
```json
{
  "email": "user@example.com",
  "password": "your_password"
}
```

**Option 2: Login with Phone Number**
```json
{
  "phone_number": "+77001234567",
  "password": "your_password"
}
```

**Optional Fields:**
- `device_token` (string, optional) - Device token for push notifications

#### cURL Example
```bash
# Production - Login with email
curl -X POST https://api.agrosearch.kz/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "your_password"
  }'

# Production - Login with phone
curl -X POST https://api.agrosearch.kz/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+77001234567",
    "password": "your_password"
  }'

# Demo
curl -X POST https://api.demo.agrosearch.kz/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "your_password"
  }'
```

#### Success Response
**Code:** `200 OK`

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 10080
}
```

**Fields:**
- `access_token` - JWT token to use in Authorization header
- `token_type` - Always "bearer"
- `expires_in` - Token expiry time in minutes (10080 = 7 days)

#### Error Responses

**Code:** `422 Unprocessable Entity` - Invalid credentials

```json
{
  "message": "The given data was invalid.",
  "errors": {
    "phone_number": ["Wrong credentials"],
    "email": ["Wrong credentials"]
  }
}
```

**Code:** `422 Unprocessable Entity` - Validation error

```json
{
  "message": "The given data was invalid.",
  "errors": {
    "password": ["The password field is required."]
  }
}
```

#### Using the Token

After successful login, use the `access_token` in all authenticated requests:

```bash
# Example: Create news with token
curl -X POST https://api.agrosearch.kz/api/content/news \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..." \
  -H "Content-Type: application/json" \
  -d '{...}'
```

**JavaScript Example:**
```javascript
// Login
const loginResponse = await fetch('https://api.agrosearch.kz/api/auth/login', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    email: 'user@example.com',
    password: 'your_password'
  })
});

const loginData = await loginResponse.json();
const token = loginData.access_token;

// Store token for future requests
localStorage.setItem('token', token);

// Use token in subsequent requests
const newsResponse = await fetch('https://api.agrosearch.kz/api/content/news', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    title: 'News title',
    description: 'News content',
    image_uri: 'tmp/images/image.jpg'
  })
});
```

### Refresh Token Endpoint

Refresh your JWT token before it expires.

#### Endpoint
```
POST /auth/refresh-token
```

#### Headers
```
Authorization: Bearer {your_current_token}
```

#### Success Response
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 10080
}
```

#### Error Response
**Code:** `401 Unauthorized` - Token expired

```json
{
  "message": "Session expired. Please log in again."
}
```

### Logout Endpoint

Invalidate your current token.

#### Endpoint
```
POST /auth/logout
```

#### Headers
```
Authorization: Bearer {your_token}
```

---

## Image Upload

### Upload Image Endpoint

**Important:** You must upload images FIRST before creating news.

#### Endpoint
```
POST /api/upload/image
```

#### Authentication
**Not required** - This endpoint is publicly accessible.

#### Headers
```
Content-Type: multipart/form-data
```

#### Request Body
- `image` (file, required) - Image file (jpg, jpeg, png, gif, bmp, svg, webp)

#### cURL Example
```bash
# Production
curl -X POST https://api.agrosearch.kz/api/upload/image \
  -F "image=@/path/to/your/image.jpg"

# Demo
curl -X POST https://api.demo.agrosearch.kz/api/upload/image \
  -F "image=@/path/to/your/image.jpg"
```

#### JavaScript/Fetch Example
```javascript
const formData = new FormData();
formData.append('image', imageFile);

const response = await fetch('/api/upload/image', {
  method: 'POST',
  body: formData
});

const data = await response.json();
console.log(data.data.path); // Use this path for image_uri
```

#### Success Response
**Code:** `200 OK`

```json
{
  "data": {
    "success": true,
    "path": "/storage/tmp/images/abc123def456.jpg"
  }
}
```

#### How to Use the Response
Remove the `/storage/` prefix from the path when creating news:

```javascript
const imagePath = response.data.path; // "/storage/tmp/images/abc123def456.jpg"
const imageUri = imagePath.replace('/storage/', ''); // "tmp/images/abc123def456.jpg"
```

#### Full Example with Base URL
```javascript
const formData = new FormData();
formData.append('image', imageFile);

const response = await fetch('https://api.agrosearch.kz/api/upload/image', {
  method: 'POST',
  body: formData
});

const data = await response.json();
const imageUri = data.data.path.replace('/storage/', '');
```

#### Error Response
**Code:** `422 Unprocessable Entity`

```json
{
  "message": "The given data was invalid.",
  "errors": {
    "image": [
      "The image field is required."
    ]
  }
}
```

---

## Create News Endpoint

### Endpoint
```
POST /api/content/news
```

### Authentication
This endpoint requires authentication using Bearer token (JWT).

### Headers
```
Authorization: Bearer {your_access_token}
Content-Type: application/json
Accept-Language: ru (optional, default: ru)
```

### Request Body

#### Required Fields
- `title` (string, max: 255) - News title in Russian
- `description` (string) - News content/description in Russian
- `image_uri` (string) - Main image path/URI

#### Optional Fields

**Basic Fields:**
- `subtitle` (string, max: 500) - News subtitle in Russian
- `date_publication` (date) - Publication date (default: current date)

**Translations (Kazakh):**
- `title_kk` (string, max: 255)
- `subtitle_kk` (string, max: 500)
- `description_kk` (string)

**Translations (English):**
- `title_en` (string, max: 255)
- `subtitle_en` (string, max: 500)
- `description_en` (string)

**SEO Fields:**
- `seo_title` (string, max: 255) - Default: uses title
- `seo_title_kk` (string, max: 255)
- `seo_title_en` (string, max: 255)
- `seo_description` (string, max: 500) - Default: uses subtitle
- `seo_description_kk` (string, max: 500)
- `seo_description_en` (string, max: 500)
- `seo_keywords` (string, max: 255)
- `seo_keywords_kk` (string, max: 255)
- `seo_keywords_en` (string, max: 255)
- `seo_image` (string) - Default: uses image_uri

**Additional Fields:**
- `tag_ids` (array of integers) - Array of news tag IDs
- `sliders` (array of strings) - Array of image paths for news slider

### Request Example

```bash
# cURL Example (Production)
curl -X POST https://api.agrosearch.kz/api/content/news \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Новый урожай пшеницы 2025",
    "title_kk": "2025 жылғы жаңа бидай өнімі",
    "title_en": "New Wheat Harvest 2025",
    "subtitle": "Рекордный урожай в этом году",
    "subtitle_kk": "Биылғы рекордтық өнім",
    "subtitle_en": "Record harvest this year",
    "description": "Подробное описание новости о урожае пшеницы...",
    "description_kk": "Бидай өнімі туралы жаңалықтың толық сипаттамасы...",
    "description_en": "Detailed description of wheat harvest news...",
    "image_uri": "tmp/images/wheat-harvest-2025.jpg",
    "seo_title": "Урожай пшеницы 2025 - Последние новости",
    "seo_description": "Узнайте о рекордном урожае пшеницы в 2025 году",
    "seo_keywords": "пшеница, урожай, 2025, сельское хозяйство",
    "seo_image": "tmp/images/wheat-harvest-seo.jpg",
    "date_publication": "2025-10-15 10:00:00",
    "tag_ids": [1, 5, 8],
    "sliders": [
      "tmp/images/wheat-1.jpg",
      "tmp/images/wheat-2.jpg",
      "tmp/images/wheat-3.jpg"
    ]
  }'
```

**JSON Payload:**
```json
{
  "title": "Новый урожай пшеницы 2025",
  "title_kk": "2025 жылғы жаңа бидай өнімі",
  "title_en": "New Wheat Harvest 2025",
  "subtitle": "Рекордный урожай в этом году",
  "subtitle_kk": "Биылғы рекордтық өнім",
  "subtitle_en": "Record harvest this year",
  "description": "Подробное описание новости о урожае пшеницы...",
  "description_kk": "Бидай өнімі туралы жаңалықтың толық сипаттамасы...",
  "description_en": "Detailed description of wheat harvest news...",
  "image_uri": "tmp/images/wheat-harvest-2025.jpg",
  "seo_title": "Урожай пшеницы 2025 - Последние новости",
  "seo_description": "Узнайте о рекордном урожае пшеницы в 2025 году",
  "seo_keywords": "пшеница, урожай, 2025, сельское хозяйство",
  "seo_image": "tmp/images/wheat-harvest-seo.jpg",
  "date_publication": "2025-10-15 10:00:00",
  "tag_ids": [1, 5, 8],
  "sliders": [
    "tmp/images/wheat-1.jpg",
    "tmp/images/wheat-2.jpg",
    "tmp/images/wheat-3.jpg"
  ]
}
```

### Success Response

**Code:** `201 Created`

```json
{
  "success": true,
  "message": "News created successfully",
  "data": {
    "id": 123,
    "title": "Новый урожай пшеницы 2025",
    "subtitle": "Рекордный урожай в этом году",
    "content": "Подробное описание новости о урожае пшеницы...",
    "image": "https://api.agrosearch.kz/storage/tmp/images/wheat-harvest-2025.jpg",
    "sliders": [
      "https://api.agrosearch.kz/storage/tmp/images/wheat-1.jpg",
      "https://api.agrosearch.kz/storage/tmp/images/wheat-2.jpg",
      "https://api.agrosearch.kz/storage/tmp/images/wheat-3.jpg"
    ],
    "create_date": 1697360400,
    "date_publication": 1697360400,
    "seo_title": "Урожай пшеницы 2025 - Последние новости",
    "seo_description": "Узнайте о рекордном урожае пшеницы в 2025 году",
    "seo_keywords": "пшеница, урожай, 2025, сельское хозяйство",
    "seo_image": "https://api.agrosearch.kz/storage/tmp/images/wheat-harvest-seo.jpg",
    "slug": "novyy-urozhay-pshenitsy-2025"
  }
}
```

### Error Responses

**Code:** `422 Unprocessable Entity`

```json
{
  "message": "The given data was invalid.",
  "errors": {
    "title": [
      "The title field is required."
    ],
    "description": [
      "The description field is required."
    ]
  }
}
```

**Code:** `401 Unauthorized`

```json
{
  "message": "Unauthenticated."
}
```

**Code:** `500 Internal Server Error`

```json
{
  "success": false,
  "message": "Failed to create news",
  "error": "Error details here"
}
```

### Notes

1. **SEO Slug**: The `seo_slug` is automatically generated from the title when creating news.
2. **Image Upload**: Images should be uploaded first using the existing image upload API endpoint (`POST /api/upload/image`), then use the returned path in `image_uri` field.
3. **Date Format**: `date_publication` accepts any valid date format (e.g., "2025-10-15", "2025-10-15 10:00:00").
4. **Tags**: Tag IDs must exist in the `handbook_news_tags` table.
5. **Cache**: The news cache is automatically cleared after creating new news.
6. **Translations**: If translation fields are not provided, the API will use the default Russian values.

### Related Endpoints

- **Get News List**: `GET /api/content/news`
- **Get Single News**: `GET /api/content/news/{slug}`
- **Upload Image**: `POST /api/upload/image`

### Permissions

Only authenticated users can create news. Additional role-based permissions may apply depending on your system configuration.

