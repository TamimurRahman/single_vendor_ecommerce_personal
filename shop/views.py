from django.shortcuts import render,redirect,get_object_or_404
from django.contrib.auth import login,authenticate,logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.db.models import Min, Max, Avg, Q
from . import models
from .forms import RegistrationForm, RatingForms, CheckoutForm
from django.contrib.auth.decorators import login_required
# Create your views here.

def home(request):
    featured_products = models.Product.objects.filter(available=True).order_by('-created')[:8]
    categories = models.Category.objects.all()
    context = {
        'featured_products':featured_products,
        'categories':categories,
    }
    return render(request,'home.html',context)

def product_list(request,category_slug=None):
    category = None
    categories = models.Category.objects.all()
    products = models.Product.objects.filter(available=True)

    if category_slug:
        category = get_object_or_404(models.Category,slug=category_slug)
        products = products.filter(category=category)
    
    min_price = products.aggregate(Min('price'))['price__min']
    max_price = products.aggregate(Max('price'))['price__max']

    if request.GET.get('min_price'):
        products = products.filter(price__gte=request.GET.get('min_price'))
    if request.GET.get('max_price'):
        products = products.filter(price__lte=request.GET.get('max_price'))
    if request.GET.get('rating'):
        min_rating = request.GET.get('rating')
        products = products.annotate(avg_rating=Avg('ratings__rating')).filter(avg_rating__gte=min_rating) #aitar kaj holo suppose user 4 rating er product dekhte chasse so aita return korbe (>=4) er rating

    if request.GET.get('search'):
        query = request.GET.get('search')
        products = products.filter(
            Q(name__icontains = query)|
            Q(description__icontains = query)|
            Q(category__name__icontains = query)
        )
    
    context = {
        'category':category,
        'categories':categories,
        'products':products,
        'min_price':min_price,
        'max_price':max_price,
    }

    return render(request,'',context)

def product_detail(request,slug):
    product = get_object_or_404(models.Product,slug=slug,available=True)
    related_products = models.Product.objects.filter(category=product.category).exclude(id=product.id)
    user_rating = None
    if request.user.is_authenticate:
        try:
            user_rating = models.Rating.objects.get(product=product,user=request.user)
        except models.Rating.DoesNotExist:
            pass
    rating_form = RatingForms(instance=user_rating)
    context = {
        'product':product,
        'related_products':related_products,
        'user_rating':user_rating,
        'rating_form':rating_form,
    }
    return render(request,'',context)

@login_required
def cart_detail(request):
    try:
        cart = models.Cart.objects.get(user=request.user)
    except models.Cart.DoesNotExist:
        cart = models.Cart.objects.create(user=request.user)
    
    return render(request,'',{'cart':cart})
@login_required
def cart_add(request,product_id):
    product = get_object_or_404(models.Product,id=product_id)
    try:
        cart = models.Cart.objects.get(user=request.user)
    except:
        cart  = models.Cart.objects.create(user=request.user)
    
    try:
        cart_item = models.CartItem.objects.get(cart=cart,product=product)
        cart_item.quantity +=1
        cart_item.save()
    except models.CartItem.DoesNotExist:
        models.CartItem.objects.create(cart=cart,product=product,quantity=1)
    
    messages.success(request,f'{product.name} has been added to your cart!')
    return redirect('')
@login_required
def cart_remove(request,product_id):
    cart = get_object_or_404(models.Cart,user=request.user)
    product = get_object_or_404(models.Product,id=product_id)
    cart_item = get_object_or_404(models.CartItem,cart=cart,product=product)
    cart_item.delete()
    messages.success(request, f'{product.name} has been removed from your cart!')
    return redirect('')
@login_required
def cart_update(request,product_id):
    cart = get_object_or_404(models.Cart,user=request.user)
    product = get_object_or_404(models.Product,id=product_id)
    cart_item = get_object_or_404(models.CartItem,cart=cart,product=product)
    quantity = int(request.POST.get('quantity',1))

    if quantity <=0:
        cart_item.delete()
        messages.success(request,f'{product.name} has been removed from your cart!')
    else:
        cart_item.quantity = quantity
        cart.save()
        messages.success(request,f'cart updated successfully!')
    return  redirect('')


def checkout(request):
    try:
        cart = models.Cart.objects.get(user=request.user)
        if not cart.items.exists():
            messages.warning(request,'your cart is empty!')
            return redirect('')
    except models.Cart.DoesNotExist:
        messages.warning(request,'Your cart is empty!')
        return redirect('')
    
    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.save()

            for item in cart.items.all():
                models.OrderItem.objects.create(
                    order = order,
                    product=item.product,
                    price = item.product.price,
                    quantity = item.quantity,
                )
            cart.items.all().delete()
            request.session['order_id'] = order.id
            return redirect('')
    else:
        initial_data={}
        if request.user.first_name:
            initial_data['first_name']=request.user.first_name
        if request.user.last_name:
            initial_data['last_name']=request.user.last_name
        if request.user.email:
            initial_data['email'] = request.user.email
        
        form = CheckoutForm(initial=initial_data)
        return render(request,'',{'cart':cart,'form':form})


def login_view(request):
    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == "POST":
        if form.is_valid():  
            user = form.get_user()
            login(request, user)
            return redirect("home")
        else:
            messages.error(request, "Invalid username or password")

    return render(request, "shop/login.html", {"form": form})

#alternative login er khetre amr manually HTML file make korte hobe
'''

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("home")
        else:
            messages.error(request, "Invalid username or password")

    return render(request, "shop/login.html")

'''
def register_view(request):
    if request.method =='POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request,user)
            messages.success(request,'Registration Successful!')
            return redirect('home')
    else:
        form = RegistrationForm()
    return render(request,'shop/register.html', {'form':form})

def logout_view(request):
    logout(request)
    return redirect('home')


       