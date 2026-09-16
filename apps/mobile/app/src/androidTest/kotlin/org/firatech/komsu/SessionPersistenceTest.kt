package org.firatech.komsu

import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test
import java.util.UUID

class SessionPersistenceTest {
    @Test fun invalidationPreservesOfflineTenantAndRenewal() {
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        val tenant=UUID.randomUUID().toString()
        val store=SessionStore(context)
        store.save("https://example.com","x".repeat(32),tenant,System.currentTimeMillis()+60000)
        assertEquals(tenant,SessionStore(context).read()?.third)
        store.invalidate()
        val reopened=SessionStore(context)
        assertNull(reopened.read())
        assertEquals(tenant,reopened.tenant())
        assertTrue(reopened.needsLogin())
        reopened.save("https://example.com","y".repeat(32),tenant,System.currentTimeMillis()+60000)
        assertEquals("y".repeat(32),SessionStore(context).read()?.second)
        reopened.invalidate()
    }
}
