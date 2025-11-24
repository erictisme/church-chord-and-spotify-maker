# Testing Guide: New Features

## ✅ What's New

### 1. Split-Screen Layout
- **Left Panel**: Song selection and controls
- **Right Panel**: Live preview (updates automatically)

### 2. AI Song Suggestions
- **Button**: Purple "🤖 AI Song Suggestions" button in Service Details
- **Settings**: ⚙️ button to configure API key

---

## 🧪 Testing Steps

### Test 1: Split-Screen Layout
1. Open https://erictisme.github.io/church-chord-and-spotify-maker/
2. **Expected**: Screen should be split 50/50
   - Left: Song selection interface
   - Right: "Live Chord Sheet Preview" panel
3. Select a song from the grid
4. **Expected**: Right panel updates automatically with chord sheet

### Test 2: Live Auto-Generation
1. Select 2-3 songs
2. **Expected**: Right panel shows chord sheets immediately
3. Change a key (dropdown next to song)
4. **Expected**: Right panel updates within 500ms
5. Adjust capo setting
6. **Expected**: Shows both capo and non-capo versions

### Test 3: AI Song Suggestions

#### Setup API Key:
1. Click the ⚙️ button (next to AI Song Suggestions)
2. Get a free API key: https://makersuite.google.com/app/apikey
3. Paste key and click "Save API Key"
4. **Expected**: Alert "API key saved successfully!"

#### Test AI Suggestions:
1. Fill in Scripture: `John 3:16-17`
2. Fill in Theme: `God's love and salvation`
3. Click "🤖 AI Song Suggestions"
4. **Expected**:
   - Button shows "⏳ Generating..."
   - Blue panel appears below
   - After 5-10 seconds: AI suggests 4 songs with detailed analysis

---

## 🐛 Troubleshooting

### "I don't see the split screen"
- **Clear cache**: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)
- **Check URL**: Must be https://erictisme.github.io/church-chord-and-spotify-maker/
- **Wait 2 minutes**: GitHub Pages may still be deploying

### "AI Suggestions not working"
- Check API key is saved (⚙️ → should show saved key)
- Check browser console (F12) for errors
- Verify API key is valid at https://makersuite.google.com/app/apikey

### "Right panel not updating"
- Open browser console (F12)
- Look for errors
- Try refreshing the page

---

## 🔍 Quick Feature Check

Run this in browser console (F12):

```javascript
// Check if AI features exist
console.log('AI Button:', document.getElementById('aiSuggestBtn') ? '✅' : '❌');
console.log('AI Settings:', document.getElementById('aiSettingsBtn') ? '✅' : '❌');
console.log('Split Screen:', document.querySelector('.left-panel') ? '✅' : '❌');
console.log('Right Panel:', document.querySelector('.right-panel') ? '✅' : '❌');

// Check if API key is saved
const apiKey = localStorage.getItem('gemini_api_key');
console.log('API Key Saved:', apiKey ? '✅ (length: ' + apiKey.length + ')' : '❌ Not saved');
```

---

## 📝 Test API Key (For Quick Testing)

If you don't have a Gemini API key yet, you can use this test prompt to verify the UI works:

1. Click ⚙️
2. Enter any text (e.g., "test123")
3. Click "Save API Key"
4. Expected: Alert shows "API key saved successfully!"
5. Click ⚙️ again
6. Expected: Input field shows "test123"

(Note: AI won't work with fake key, but you can verify the UI and storage)

---

## ✨ Expected Behavior Summary

| Feature | Expected Result |
|---------|----------------|
| Split Screen | 50/50 layout on desktop, stacked on mobile |
| Live Preview | Updates within 500ms of any change |
| AI Button | Purple button in Service Details |
| API Settings | ⚙️ button opens modal |
| API Key Storage | Saved in localStorage (persists across sessions) |
| AI Response | 4 songs with analysis in 5-10 seconds |
| Capo Feature | Shows both written and sounding keys |

---

## 🚀 Next Steps After Testing

If everything works:
- Get your own Gemini API key (free at Google AI Studio)
- Try generating suggestions for your next service
- Report any issues or suggestions!
